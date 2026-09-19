// Useful local tools. These run in the browser; no LLM or external API is involved.
window.BacSkillTools = (() => {
  const escape = value => String(value).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  function analyze(text) {
    if(text.length>65536)throw new Error('Use a CSV smaller than 64 KB.');
    const rows=[];let row=[],field='',quoted=false,closed=false;
    text=text.replace(/^\uFEFF/,'').replace(/\r\n/g,'\n').replace(/\r/g,'\n');
    for(let i=0;i<=text.length;i++){
      const ch=i===text.length?'\n':text[i];
      if(quoted){if(ch==='"'){if(text[i+1]==='"'){field+='"';i++;}else{quoted=false;closed=true;}}else field+=ch;continue;}
      if(ch==='"'){if(field||closed)throw new Error('A CSV quote is misplaced.');quoted=true;continue;}
      if(ch===','||ch==='\n') {row.push(field.trim());field='';closed=false;if(ch==='\n'){if(row.some(Boolean))rows.push(row);row=[];}continue;}
      if(closed&&ch.trim())throw new Error('Unexpected text after a quoted field.');
      field+=ch;
    }
    if(quoted)throw new Error('Close the quoted CSV field.');
    if(rows.length<2||rows.length>501)throw new Error('Use a header and between 1 and 500 data rows.');
    if(rows[0].map(v=>v.toLowerCase()).join(',')!=='topic,attendees')throw new Error('Use exactly these column headers: topic,attendees');
    const counts=new Map();let total=0;
    rows.slice(1).forEach((row,i)=>{
      if(row.length!==2||!row[0]||row[0].length>80||!/^\d+$/.test(row[1]))throw new Error('Row '+(i+2)+': provide a topic and a nonnegative whole attendee count.');
      const value=Number(row[1]);
      if(!Number.isSafeInteger(value)||value>1000000)throw new Error('Row '+(i+2)+': attendee count is too large.');
      counts.set(row[0],(counts.get(row[0])||0)+value);total+=value;
    });
    if(!total)throw new Error('Include at least one attendee.');
    const data=[...counts].map(([topic,count])=>({topic,count,share:count/total*100})).sort((a,b)=>b.count-a.count);
    const html=`<span class="pill">Calculated locally · your CSV</span><div class="pg-data-summary"><strong>${total.toLocaleString()}<small>Total attendees</small></strong><strong>${data.length}<small>Interest topics</small></strong><strong>${rows.length-1}<small>Rows checked</small></strong></div><div class="pg-chart" role="img" aria-label="Attendees by topic">${data.map((d,i)=>`<div class="pg-chart-row"><div><span>${escape(d.topic)}</span><strong>${d.count} · ${d.share.toFixed(1)}%</strong></div><span class="pg-chart-track"><i style="width:${d.share}%;opacity:${Math.max(.4,1-i*.1)}"></i></span></div>`).join('')}</div><p class="notice">Duplicate topics are combined. Percentages use ${total} total attendees. This is a local calculation, not an LLM answer.</p><button class="action primary pg-download" id="pg-download">Download report .md ↓</button>`;
    const report='# Audience interest report\n\nCalculated from your CSV in this browser.\n\nTotal attendees: '+total+'\nData rows: '+(rows.length-1)+'\n\n| Topic | Attendees | Share |\n|---|---:|---:|\n'+data.map(d=>'| '+d.topic.replace(/[|\n]/g,' ')+' | '+d.count+' | '+d.share.toFixed(1)+'% |').join('\n')+'\n\nMethod: sum repeated topics; divide each topic count by the total. No external service or LLM was used.\n';
    return {html,report,total,topics:data.length};
  }
  function poster(request,canvas) {
    canvas.width=1080;canvas.height=1350;
    const ctx=canvas.getContext('2d');
    ctx.fillStyle='#0e100c';ctx.fillRect(0,0,1080,1350);
    ctx.fillStyle='#76b900';ctx.fillRect(0,0,1080,14);
    ctx.fillStyle='#ecf0e5';ctx.font='bold 31px Arial';ctx.fillText('NVIDIA',72,96);
    ctx.fillStyle='#a2b18c';ctx.font='19px Arial';ctx.fillText('BUILD A CLAW / COMMUNITY EVENT',72,141);
    const wording={en:['BUILD.','CONNECT.','CREATE.','HANDS-ON AI EXPERIENCE'],ko:['만들고.','연결하고.','체험하세요.','직접 만드는 AI 경험'],ja:['つくる。','つながる。','体験する。','ハンズオン AI 体験']}[request.language];
    // Procedural artwork: five stations connect to one shared center.
    const cx=755,cy=490;
    ctx.strokeStyle='#4e752a';ctx.lineWidth=2;
    for(let i=0;i<6;i++){ctx.beginPath();ctx.ellipse(cx,cy,70+i*31,47+i*22,-.3,0,Math.PI*2);ctx.stroke();}
    for(let i=0;i<5;i++){const a=i*Math.PI*2/5;const x=cx+Math.cos(a)*202,y=cy+Math.sin(a)*155;ctx.beginPath();ctx.moveTo(cx,cy);ctx.lineTo(x,y);ctx.stroke();ctx.fillStyle='#b4ea72';ctx.fillRect(x-24,y-24,48,48);ctx.fillStyle='#173006';ctx.fillRect(x-13,y-5,7,7);ctx.fillRect(x+6,y-5,7,7);}
    ctx.fillStyle='#76b900';ctx.fillRect(cx-40,cy-40,80,80);
    ctx.font='bold 70px Arial';ctx.fillStyle='#f3f6eb';wording.slice(0,3).forEach((line,i)=>ctx.fillText(line,72,307+i*86,680));
    ctx.fillStyle='#97cb52';ctx.font='18px Arial';ctx.fillText(wording[3],72,608);
    ctx.strokeStyle='#414e34';ctx.beginPath();ctx.moveTo(72,658);ctx.lineTo(1008,658);ctx.stroke();
    function wrap(text,x,y,maxWidth,lineHeight,font,color){ctx.font=font;ctx.fillStyle=color;let line='',lineIndex=0;for(const char of text){if(ctx.measureText(line+char).width>maxWidth){ctx.fillText(line,x,y+lineIndex*lineHeight);lineIndex++;line=char;}else line+=char;}if(line)ctx.fillText(line,x,y+lineIndex*lineHeight);return y+(lineIndex+1)*lineHeight;}
    const next=wrap(request.title,72,752,930,64,'bold 54px Arial','#f2f5e9');
    wrap(request.tagline,72,next+20,920,35,'25px Arial','#b9c9a6');
    ctx.fillStyle='#76b900';ctx.fillRect(72,1050,936,118);ctx.fillStyle='#132007';ctx.font='bold 33px Arial';ctx.fillText(request.city,99,1100,870);ctx.font='22px Arial';ctx.fillText(request.details,99,1140,870);
    ctx.fillStyle='#b3c69b';ctx.font='18px Arial';ctx.fillText('EVENT DRAFT / DATE, VENUE AND REGISTRATION TO BE CONFIRMED',72,1245,936);
    ctx.fillStyle='#6e805b';ctx.font='15px Arial';ctx.fillText('Created with the BaC local poster tool. Not an official NVIDIA template.',72,1290,936);
    return canvas;
  }
  function download(blob,name){const url=URL.createObjectURL(blob),link=document.createElement('a');link.href=url;link.download=name;link.click();setTimeout(()=>URL.revokeObjectURL(url),3000);}
  return {analyze,poster,download};
})();
