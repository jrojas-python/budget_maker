import logging

from weasyprint import HTML

logger = logging.getLogger(__name__)


class PdfService:
    """Genera PDFs a partir de contenido HTML."""

    def generate_from_html(self, html_content: str) -> bytes:
        """Convierte HTML a bytes PDF."""
        pdf_bytes = HTML(string=html_content).write_pdf()
        logger.info("PDF generado: %d bytes", len(pdf_bytes))
        return pdf_bytes
