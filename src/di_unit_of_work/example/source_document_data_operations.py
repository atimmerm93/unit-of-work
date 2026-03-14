from di_unit_of_work.base_dao import BaseDao
from di_unit_of_work.example.orm_model import SourceDocument
from di_unit_of_work.session_provider import SessionProvider
from di_unit_of_work.transactional_decorator import transactional


class SourceDocumentDataOperations(BaseDao):
    def __init__(self, session_provider: SessionProvider) -> None:
        self._session_provider = session_provider

    @transactional
    def create_source_document(
        self, file_path: str = "/path/to/file", file_hash: str = "somehash"
    ) -> None:
        # Here you would typically create a new SourceDocument instance and add it to the session
        # For example:
        new_source_document = SourceDocument(file_path=file_path, file_hash=file_hash)
        self._add_to_db(new_source_document)
        print(f"Created source document: {new_source_document.file_path}")
