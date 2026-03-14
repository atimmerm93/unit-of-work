from python_di_application.dependency import Dependency
from python_di_application.di_container import DIContainer

from di_unit_of_work.example.orm_model import Base, SourceDocument
from di_unit_of_work.example.source_document_data_operations import SourceDocumentDataOperations
from di_unit_of_work.session_aspect import SessionAspect
from di_unit_of_work.session_cache import SessionCache
from di_unit_of_work.session_factory.sqlite_session_factory import SQLiteSessionFactory, SqlLiteConfig
from di_unit_of_work.session_provider import SessionProvider


def main() -> None:
    container = DIContainer()
    container.register_dependencies(dependencies_types_with_kwargs=
                                    [Dependency(SourceDocumentDataOperations),
                                     Dependency(SessionProvider),
                                     Dependency(SQLiteSessionFactory),
                                     Dependency(SessionAspect),
                                     Dependency(SessionCache)])
    container.register_instance(
        instance_obj=SqlLiteConfig(
            path=":memory:",
            metadata=Base.metadata,
        )
    )
    data_operations = container[SourceDocumentDataOperations]
    session_factory = container[SQLiteSessionFactory]
    container.apply_post_init_wrappers()
    data_operations.create_source_document()
    with session_factory() as sess:
        print(sess.query(SourceDocument).all()[0].file_path)


if __name__ == "__main__":
    # Example usage
    main()
