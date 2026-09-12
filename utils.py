import os

from pypdf import PdfReader
from docx import Document
from pptx import Presentation
from openpyxl import load_workbook


def extract_text(file_path):

    extension = os.path.splitext(file_path)[1].lower()

    print("=" * 60)
    print("TEXT EXTRACTION")
    print("File:", os.path.basename(file_path))
    print("Extension:", extension)
    print("=" * 60)

    try:

        # --------------------------------------------------
        # PDF
        # --------------------------------------------------

        if extension == ".pdf":

            reader = PdfReader(file_path)

            text = []

            for page in reader.pages:

                page_text = page.extract_text()

                if page_text:
                    text.append(page_text)

            result = "\n".join(text)

        # --------------------------------------------------
        # DOCX
        # --------------------------------------------------

        elif extension == ".docx":

            document = Document(file_path)

            text = []

            # Paragraphs
            for paragraph in document.paragraphs:

                if paragraph.text.strip():
                    text.append(
                        paragraph.text.strip()
                    )

            # Tables
            for table in document.tables:

                for row in table.rows:

                    row_text = []

                    for cell in row.cells:

                        if cell.text.strip():
                            row_text.append(
                                cell.text.strip()
                            )

                    if row_text:
                        text.append(
                            " | ".join(row_text)
                        )

            result = "\n".join(text)

        # --------------------------------------------------
        # PPTX
        # --------------------------------------------------

        elif extension == ".pptx":

            presentation = Presentation(file_path)

            text = []

            for slide_number, slide in enumerate(
                presentation.slides,
                start=1
            ):

                slide_text = []

                for shape in slide.shapes:

                    if hasattr(shape, "text"):

                        shape_text = shape.text.strip()

                        if shape_text:
                            slide_text.append(
                                shape_text
                            )

                if slide_text:

                    text.append(
                        f"Slide {slide_number}\n"
                        + "\n".join(slide_text)
                    )

            result = "\n\n".join(text)

        # --------------------------------------------------
        # TXT
        # --------------------------------------------------

        elif extension == ".txt":

            with open(
                file_path,
                "r",
                encoding="utf-8",
                errors="ignore"
            ) as file:

                result = file.read()

        # --------------------------------------------------
        # XLSX
        # --------------------------------------------------

        elif extension == ".xlsx":

            workbook = load_workbook(
                file_path,
                read_only=True,
                data_only=True
            )

            text = []

            for worksheet in workbook.worksheets:

                text.append(
                    f"Sheet: {worksheet.title}"
                )

                for row in worksheet.iter_rows(
                    values_only=True
                ):

                    values = []

                    for value in row:

                        if value is not None:
                            values.append(
                                str(value)
                            )

                    if values:
                        text.append(
                            " | ".join(values)
                        )

            workbook.close()

            result = "\n".join(text)

        # --------------------------------------------------
        # Unsupported
        # --------------------------------------------------

        else:

            result = ""

        print(
            "Extracted text length:",
            len(result)
        )

        if result.strip():

            print("✅ Text extraction successful")

        else:

            print("❌ No text extracted")

        return result

    except Exception as e:

        print(
            "❌ Text extraction error:",
            str(e)
        )

        return ""