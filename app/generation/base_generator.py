from abc import ABC, abstractmethod
from app.schemas.tailored_cv import TailoredCV


class BaseGenerator(ABC):
    """
    Abstract base for all CV output generators.
    Every generator takes a TailoredCV and returns bytes.
    The API layer writes those bytes to an HTTP response.
    """

    @abstractmethod
    def generate(self, cv: TailoredCV, section_config: dict | None = None) -> bytes:
        """
        Generate a CV document from a TailoredCV model.
        Returns raw bytes of the generated file.
        """
        ...

    @abstractmethod
    def content_type(self) -> str:
        """
        Returns the MIME type of the generated file.
        Used by the API layer to set Content-Type header.
        """
        ...

    @abstractmethod
    def file_extension(self) -> str:
        """
        Returns the file extension without the dot.
        Used to construct the download filename.
        """
        ...

    def filename(self, cv: TailoredCV) -> str:
        """
        Constructs a clean download filename from CV metadata.
        e.g. 'moaaz_emam_acme_corp.docx'
        """
        name = cv.full_name.lower().replace(" ", "_")
        company = cv.company_name.lower().replace(" ", "_")
        return f"{name}_{company}.{self.file_extension()}"