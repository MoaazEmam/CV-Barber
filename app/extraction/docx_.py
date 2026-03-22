from docx import Document

class DocxExtractor:
    def extract_text(self,path:str)->str:
        doc=Document(path)
        lines:list[str]=[]

        for paragraph in doc.paragraphs:
            text=paragraph.text.strip()
            if text:
                lines.append(text)
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    text=cell.text.strip()
                    if text:
                        lines.append(text)
        return "\n".join(lines)