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
    def test_all_text_formats_accept_ten_megabytes_and_reject_more(self):
        for name in ('notes.txt','notes.md','notes.csv'):
            with self.subTest(name=name):
                content='x'*MAX_TEXT
                raw,extra=decode_document(name,{'content':content})
                self.assertEqual(len(raw),10*1024*1024);self.assertIsNone(extra)
                with self.assertRaisesRegex(ValueError,'10 MB'):
                    decode_document(name,{'content':content+'x'})
        with self.assertRaisesRegex(ValueError,'10 MB'):
            decode_document('unicode.txt',{'content':'가'*(MAX_TEXT//3+1)})

    def test_uploads_and_prompts_stay_with_selected_agent_in_both_modes(self):
        for protection in ('standard', 'openshell'):
            with self.subTest(protection=protection), tempfile.TemporaryDirectory() as d:
                adapter=Adapter();studio=Studio(d,adapter,start_worker=False)
                owner=studio.session()[0]['id']
                studio.onboard(owner,{'name':'First','skills':['documents'],'protection':protection})
                if (job:=studio.next_job()):studio.execute(job)
                other=studio.add_agent(owner,{'name':'Second','skills':['documents']})['agentId']
                studio.upload(owner,{'name':'private.txt','content':'first-private-nonce'})
                self.assertEqual(studio.state(other)['files'],[])
                with self.assertRaises(Problem):studio.available_file(other,'inbox/private.txt')
                with self.assertRaises(Problem):studio.available_file(other,'inbox/../../'+owner+'/inbox/private.txt')
                studio.upload(other,{'name':'private.txt','content':'second-private-nonce'})
                self.assertEqual(studio.available_file(owner,'inbox/private.txt').read_text(),'first-private-nonce')
                self.assertEqual(studio.available_file(other,'inbox/private.txt').read_text(),'second-private-nonce')
                studio.upload(owner,{'name':'owner-only.md','content':'Only first sees this.'})
                studio.enqueue(other,{'kind':'chat','prompt':'Read my document.'})
                studio.execute(studio.next_job())
                self.assertIn('inbox/private.txt',adapter.calls[-1][2])
                self.assertNotIn('owner-only.md',adapter.calls[-1][2])

    def test_in_flight_workspace_sync_cannot_race_an_upload(self):
        with tempfile.TemporaryDirectory() as d:
            studio=Studio(d,Adapter(),start_worker=False);owner=studio.session()[0]['id']
            studio.onboard(owner,{'name':'Reader','skills':['documents'],'protection':'openshell'})
            studio.execute(studio.next_job())
            studio.upload(owner,{'name':'notes.txt','content':'original'})
            studio.executing_owners.add(owner)
            with self.assertRaises(Problem):studio.upload(owner,{'name':'notes.txt','content':'replacement'})
            self.assertEqual(studio.available_file(owner,'inbox/notes.txt').read_text(),'original')
            studio.executing_owners.clear()
            studio.upload(owner,{'name':'notes.txt','content':'replacement'})
            self.assertEqual(studio.available_file(owner,'inbox/notes.txt').read_text(),'replacement')
            studio.delete_agent(owner,{'name':'Reader'},enqueue_only=True)
            with self.assertRaises(Problem):studio.upload(owner,{'name':'late.txt','content':'late'})
            self.assertFalse((studio.workspace(owner)/'inbox/late.txt').exists())

    def test_existing_document_can_be_replaced_at_capacity(self):
        with tempfile.TemporaryDirectory() as d:
            studio=Studio(d,Adapter(),start_worker=False);owner=studio.session()[0]['id']
            studio.onboard(owner,{'name':'Reader','skills':['documents']})
            for index in range(80):studio.upload(owner,{'name':str(index)+'.txt','content':'old'})
            studio.upload(owner,{'name':'0.txt','content':'updated'})
            self.assertEqual(studio.available_file(owner,'inbox/0.txt').read_text(),'updated')
            with self.assertRaises(Problem):studio.upload(owner,{'name':'81.txt','content':'overflow'})

    def test_large_successful_upload_is_listed_readable_and_in_agent_prompt(self):
        with tempfile.TemporaryDirectory() as d:
            adapter=Adapter();studio=Studio(d,adapter,start_worker=False);owner=studio.session()[0]['id']
            studio.onboard(owner,{'name':'Reader','skills':['documents']})
            studio.upload(owner,{'name':'large.txt','content':'x'*MAX_TEXT})
            self.assertEqual(studio.state(owner)['files'][0]['size'],MAX_TEXT)
            self.assertEqual(studio.available_file(owner,'inbox/large.txt').stat().st_size,MAX_TEXT)
            studio.enqueue(owner,{'kind':'chat','prompt':'Summarize my uploaded file.'})
            studio.execute(studio.next_job())
            self.assertIn('inbox/large.txt',adapter.calls[-1][2])

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
