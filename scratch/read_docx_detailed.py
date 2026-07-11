import zipfile
import xml.etree.ElementTree as ET
import sys

def parse_docx(path):
    ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
    try:
        with zipfile.ZipFile(path) as z:
            doc_xml = z.read('word/document.xml')
            root = ET.fromstring(doc_xml)
            
            body = root.find('w:body', ns)
            if body is None:
                return "Could not find body in docx."
            
            output = []
            # We iterate over children of body in order
            for child in body:
                if child.tag == '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p':
                    # Paragraph
                    texts = [t.text for t in child.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t') if t.text]
                    if texts:
                        output.append(''.join(texts))
                elif child.tag == '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}tbl':
                    # Table
                    table_data = []
                    for row in child.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}tr'):
                        row_data = []
                        for cell in row.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}tc'):
                            cell_text = ''.join([t.text for t in cell.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t') if t.text])
                            row_data.append(cell_text.strip())
                        table_data.append(row_data)
                    
                    # Format table
                    if table_data:
                        col_widths = [max(len(str(cell)) for cell in col) for col in zip(*table_data)]
                        table_str = []
                        for row in table_data:
                            row_str = " | ".join(f"{str(cell):<{col_widths[i]}}" for i, cell in enumerate(row))
                            table_str.append("| " + row_str + " |")
                        output.append("\n" + "\n".join(table_str) + "\n")
            
            return "\n".join(output)
    except Exception as e:
        return f"Error reading {path}: {str(e)}"

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python read_docx_detailed.py <path_to_docx>")
        sys.exit(1)
    print(parse_docx(sys.argv[1]))
