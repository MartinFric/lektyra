"""Profile pictures (ADR-015): a face next to a name, so Martin sees at a glance who a name is.

A picture belongs to a named person: an unnamed voice has no face yet. It comes from a file Martin drops into the
UI, from Wikidata's image of the person (Wikimedia Commons, with licence and author), or from an address (the
`profile-pictures` skill). lektyra re-encodes every picture before it keeps it. The file lives in lektyra's own
MinIO under `persons/<person key>/<version>.webp`; the database holds which object it is and where it came from.

Objects are written before rows and deleted after them, so a failure in between leaves an object nobody points at,
never a row without its picture. `sweep` deletes those leftovers: when the UI starts and after a person is forgotten.
"""

import logging
from typing import Final

from lektyra.adapters.images.pictures import normalise_picture
from lektyra.adapters.knowledge.wikimedia import QID, WikidataHit, Wikimedia
from lektyra.adapters.objects.s3 import S3Objects
from lektyra.adapters.store.postgres import PersonFields, PersonRow, PhotoSource, Store
from lektyra.errors import LektyraError
from lektyra.ports import ObjectStore
from lektyra.settings import Settings

PREFIX: Final = "persons/"
log = logging.getLogger("lektyra.photos")


class NoPictureStore:
    """What runs without a login for the picture store: everything else works, pictures say why they do not."""

    def __init__(self, reason: str) -> None:
        self._reason = reason

    def _off(self) -> LektyraError:
        return LektyraError("unavailable", self._reason)

    def put(self, key: str, data: bytes, content_type: str) -> None:
        raise self._off()

    def get(self, key: str) -> bytes:
        raise self._off()

    def delete(self, key: str) -> None:
        raise self._off()

    def keys(self, prefix: str) -> list[str]:
        raise self._off()


def open_objects(settings: Settings) -> ObjectStore:
    """lektyra's MinIO from settings (`~/.secrets/lektyra-minio.env`). Nothing is contacted yet: a store that is down
    now works once it is up, and the bucket is made by the first picture."""
    user, password = settings.minio_root_user, settings.minio_root_password
    if user is None or password is None:
        return NoPictureStore("No login for the picture store: ~/.secrets/lektyra-minio.env is missing.")
    return S3Objects(settings.minio_url, user.get_secret_value(), password.get_secret_value(), settings.pictures_bucket)


class Photos:
    def __init__(self, store: Store, objects: ObjectStore, actor: str, wikimedia: Wikimedia | None = None) -> None:
        self._store = store
        self._objects = objects
        self._actor = actor
        self._wikimedia = wikimedia or Wikimedia()

    def _named(self, person_id: int) -> PersonRow:
        person = self._store.person(person_id)
        if person.anonymous:
            raise LektyraError("conflict", f"{person.name} has no name yet. Name the voice first; then add a picture.")
        return person

    def get(self, person_id: int) -> tuple[bytes, str]:
        row = self._store.photo(person_id)
        return self._objects.get(row.object_key), row.content_type

    def upload(self, person_id: int, raw: bytes, source: PhotoSource | None = None) -> PersonRow:
        person = self._named(person_id)
        picture = normalise_picture(raw)
        key = f"{PREFIX}{person.key}/{picture.version}.webp"
        old = self._store.photo(person_id).object_key if person.photo else None
        self._objects.put(key, picture.data, picture.content_type)
        self._store.save_photo(
            person_id,
            key,
            (picture.width, picture.height),
            picture.version,
            picture.content_type,
            source or PhotoSource(),
            self._actor,
        )
        if old is not None and old != key:
            self._objects.delete(old)
        return self._store.person(person_id)

    def from_wikidata(self, person_id: int, qid: str | None = None) -> PersonRow:
        """The picture Wikidata has for the person (its knowledge link, or `qid`). With `qid` and no knowledge link
        yet, the person gets that link too: the picture says which item they are."""
        person = self._named(person_id)
        linked = person.external_ref if person.external_ref and QID.match(person.external_ref) else None
        item = qid or linked
        if item is None:
            raise LektyraError("invalid", "Put the person's Wikidata id (Q…) in the knowledge link first.")
        found = self._wikimedia.picture(item)
        if found is None:
            raise LektyraError("not_found", f"Wikidata has no picture of {person.name} ({item}).")
        source = PhotoSource(source_url=found.page_url, license=found.license, author=found.author)
        saved = self.upload(person_id, self._wikimedia.download(found.image_url), source)
        if not person.external_ref:
            fields = PersonFields(**{**person.model_dump(include=set(PersonFields.model_fields)), "external_ref": item})
            self._store.save_person(person_id, fields, self._actor)
            saved = self._store.person(person_id)
        return saved

    def from_url(self, person_id: int, url: str, source: PhotoSource) -> PersonRow:
        self._named(person_id)
        raw = self._wikimedia.download(url)
        return self.upload(person_id, raw, source.model_copy(update={"source_url": source.source_url or url}))

    def remove(self, person_id: int) -> None:
        key = self._store.photo(person_id).object_key
        self._store.delete_photo(person_id, self._actor)
        self._objects.delete(key)

    def missing(self) -> list[PersonRow]:
        """Named persons without a picture, public figures first."""
        waiting = [p for p in self._store.persons() if not p.anonymous and p.photo is None]
        return sorted(waiting, key=lambda p: not p.public_figure)

    def search(self, name: str) -> list[WikidataHit]:
        return self._wikimedia.search(name)

    def sweep(self) -> int:
        """Delete every picture no person points at (a forgotten person's, a replaced one). How many went."""
        kept = self._store.photo_keys()
        gone = [k for k in self._objects.keys(PREFIX) if k not in kept]
        for key in gone:
            self._objects.delete(key)
        if gone:
            log.info("swept %d picture(s) nobody points at", len(gone))
        return len(gone)
