import base64
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from document_upload import decode_document, MAX_TEXT
from studio import Studio, Problem
from test_studio import Adapter


def pdf_fixture(label='Hello PDF'):
    stream=('BT /F1 12 Tf 72 720 Td ('+label+') Tj ET').encode()
    objects=[b'<< /Type /Catalog /Pages 2 0 R >>',b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>',b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',b'<< /Length '+str(len(stream)).encode()+b' >>\nstream\n'+stream+b'\nendstream']
    result=b'%PDF-1.4\n';offsets=[]
    for i,obj in enumerate(objects,1):
        offsets.append(len(result));result+=str(i).encode()+b' 0 obj\n'+obj+b'\nendobj\n'
    xref=len(result);result+=b'xref\n0 6\n0000000000 65535 f \n'
    result+=b''.join(('%010d 00000 n \n'%n).encode() for n in offsets)
    return result+b'trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n'+str(xref).encode()+b'\n%%EOF'

class Documents(unittest.TestCase):
    def test_csv_preserves_rows_and_rejects_large_or_invalid_files(self):
        text='Name,Value\n"a,b",42\n';raw,extra=decode_document('표.csv',{'content':'\ufeff'+text})
        self.assertEqual(raw.decode(),text);self.assertIsNone(extra)
        for name,data in [('a.csv',{'content':'x'*(MAX_TEXT+1)}),('a.pdf',{'content':'!','encoding':'base64'}),('a.exe',{'content':'x'})]:
            with self.assertRaises(ValueError):decode_document(name,data)

    @unittest.skipUnless(shutil.which('pdftotext') and shutil.which('pdfinfo'),'Poppler required')
    def test_pdf_upload_preserves_original_and_exposes_page_text(self):
        raw=pdf_fixture();data={'name':'행사 자료.PDF','encoding':'base64','content':base64.b64encode(raw).decode()}
        with tempfile.TemporaryDirectory() as d:
            studio=Studio(d,Adapter(),start_worker=False);owner=studio.session()[0]['id']
            studio.onboard(owner,{'name':'Reader','persona':'analyst','skills':['documents']})
            result=studio.upload(owner,data)
            self.assertEqual((studio.workspace(owner)/result['path']).read_bytes(),raw)
            extracted=(studio.workspace(owner)/result['textPath']).read_text()
            self.assertIn('Page 1',extracted);self.assertIn('Hello PDF',extracted)
            self.assertEqual(len([f for f in studio.files(owner) if f['kind']=='inbox']),2)
            with self.assertRaises(Problem):studio.upload(owner,{**data,'name':'../escape.pdf'})
        with self.assertRaisesRegex(ValueError,'OCR'):
            decode_document('scan.pdf',{'encoding':'base64','content':base64.b64encode(pdf_fixture('')).decode()})

    def test_missing_pdf_tool_has_actionable_error(self):
        with patch('document_upload.shutil.which',return_value=None),self.assertRaisesRegex(ValueError,'Poppler'):
            decode_document('a.pdf',{'encoding':'base64','content':base64.b64encode(pdf_fixture()).decode()})

    def test_pptx_uses_presentation_order_and_slide_references(self):
        import io
        from zipfile import ZipFile
        out=io.BytesIO()
        with ZipFile(out,'w') as z:
            z.writestr('ppt/presentation.xml','<p:presentation xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><p:sldIdLst><p:sldId r:id="b"/><p:sldId r:id="a"/></p:sldIdLst></p:presentation>')
            z.writestr('ppt/_rels/presentation.xml.rels','<Relationships><Relationship Id="a" Target="slides/slide1.xml"/><Relationship Id="b" Target="slides/slide2.xml"/></Relationships>')
            for i,value in [(1,'Second &amp; last'),(2,'First takeaway')]:
                z.writestr('ppt/slides/slide%d.xml'%i,'<root xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"><a:p><a:r><a:t>'+value+'</a:t></a:r></a:p></root>')
        data={'encoding':'base64','content':base64.b64encode(out.getvalue()).decode()}
        raw,text=decode_document('deck.pptx',data)
        self.assertEqual(raw,out.getvalue())
        self.assertIn('Slide 1 ---\nFirst takeaway',text)
        self.assertIn('Slide 2 ---\nSecond & last',text)
        with self.assertRaisesRegex(ValueError,'Convert older'):
            decode_document('deck.ppt',data)
