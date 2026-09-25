// Browser text decoding must reject legacy/corrupt bytes instead of losing data.
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync('src/studio-chat.js','utf8');
const context=vm.createContext({TextDecoder});
vm.runInContext(source.slice(source.indexOf('async function documentText('),source.indexOf('function renderDocuments(')),context);
const file=bytes=>({arrayBuffer:async()=>Uint8Array.from(bytes).buffer});
(async()=>{
 const text='회의 일정: 10월 7일\n担当者: Nora 🦀';
 assert.equal(await context.documentText(file(Buffer.from(text))),text);
 assert.equal(await context.documentText(file(Buffer.concat([Buffer.from([239,187,191]),Buffer.from(text)]))),text);
 for(const bytes of [[0xc8,0xb8,0xc0,0xc7],[0xe2,0x82],[0xff]]){
  await assert.rejects(context.documentText(file(bytes)),/not valid UTF-8/);
 }
 // An actual replacement glyph intentionally authored in UTF-8 remains valid.
 assert.equal(await context.documentText(file(Buffer.from('literal �'))),'literal �');
 console.log('PASS: Unicode and BOM retained; CP949/corrupt UTF-8 rejected without silent replacement');
})().catch(error=>{console.error(error);process.exitCode=1});
