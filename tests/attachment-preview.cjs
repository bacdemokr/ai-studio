// Attachment preview controller and CSV parsing checks without a live server.
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync('src/studio-identity.js','utf8').split('// Uploaded documents open independently of chat navigation or attachment selection.')[1];
const escape=text=>String(text).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const requests=[],links=[],pages=[];let popup=true,failure=false,closed=false;
const tab={opener:{},get closed(){return closed;},document:{open(){},write(html){pages.push(html);},close(){},createElement:()=>({}),querySelector:()=>({after:link=>links.push(link)})}};
const context={escape,agentId:'orbit',selectedScenario:'plan',window:{open:()=>popup?tab:null},alert:message=>pages.push(message),
 api:async(path,payload,target,scenario)=>{requests.push({path,target,scenario});if(failure)throw Error('File unavailable <test>');return path.includes('xlsx')&&!path.includes('xlsx.txt')?{encoding:'base64',content:'YWJj',mime:'application/test'}:{content:'Name,Value\r\n"North, West",12'};},
 Blob,Uint8Array,atob,URL:{createObjectURL:()=> 'blob:test',revokeObjectURL(){}},setInterval:()=>1,clearInterval(){}};
vm.runInNewContext(source,context);
const rows=text=>JSON.parse(JSON.stringify(context.attachmentCsvRows(text).rows));
assert.deepEqual(rows('\uFEFFName,Notes\r\n"A, B","line 1\nline 2"\r\n"C""D",\r\n'),[['Name','Notes'],['A, B','line 1\nline 2'],['C"D','']]);
assert.deepEqual(rows('a,b\nc,d'),[['a','b'],['c','d']]);
assert.equal(context.attachmentCsvRows('a\nb\nc',2).clipped,true);
assert.equal(context.attachmentCsvRows('a,b,c',10,2).clipped,true);
const markup=context.attachmentPreviewMarkup('unsafe.csv','Name,Value\n<script>alert(1)</script>,=SUM(A1)');
assert(!markup.includes('<script>'));assert(markup.includes('&lt;script&gt;'));assert(markup.includes('=SUM(A1)'));assert(markup.includes('<table>'));
assert(context.attachmentPreviewMarkup('a.txt','<img src=x onerror=alert(1)>').includes('&lt;img'));
assert(context.attachmentPreviewMarkup('a.xlsx','Sheet A1: text',true).includes('Extracted text'));
(async()=>{
 await context.openAttachmentTab('inbox/data.csv','0');
 assert.equal(tab.opener,null);assert.equal(requests[0].target,'orbit');assert.equal(requests[0].scenario,'plan');assert(requests[0].path.includes('workspace=0'));
 assert.equal(links[0].download,'data.csv');assert(pages.at(-1).includes('<table>'));assert(pages.at(-1).includes("default-src 'none'"));
 await context.openAttachmentTab('inbox/book.xlsx','0');assert(requests.at(-1).path.includes('book.xlsx.txt'));assert.equal(links.at(-1).download,'book.xlsx');
 failure=true;await context.openAttachmentTab('inbox/missing.txt','0');assert(pages.at(-1).includes('File unavailable &lt;test&gt;'));
 const before=requests.length;popup=false;await context.openAttachmentTab('inbox/data.csv','0');assert.equal(requests.length,before);assert(pages.at(-1).includes('Allow pop-ups'));
 popup=true;closed=true;const renders=pages.length;await context.openAttachmentTab('inbox/data.csv','0');assert.equal(pages.length,renders);
 console.log('PASS: CSV quoting/limits, escaped content, captured workspace, separate tab, binary text preview/download, errors and blocked/closed tabs.');
})().catch(error=>{console.error(error);process.exitCode=1;});
