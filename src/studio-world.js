  // Included in Studio's closure. Keep dialogs inside the fullscreen root.
  const worldViewport=document.getElementById('campus-viewport');
  const worldButton=document.createElement('button');
  worldButton.id='studio-focus';worldButton.type='button';
  worldButton.textContent='Full screen ↗';worldButton.title='Full screen · Enter after selecting the 3D view';
  worldButton.setAttribute('aria-controls','campus-viewport');worldButton.setAttribute('aria-expanded','false');
  document.querySelector('.campus-scene-bottom .row').prepend(worldButton);
  worldViewport.tabIndex=0;worldViewport.setAttribute('role','region');
  worldViewport.setAttribute('aria-keyshortcuts','Enter');
  worldViewport.setAttribute('aria-label','Interactive 3D workshop. Click then press Enter for full screen, or double-click an empty area. Drag to orbit and scroll to zoom. Escape returns to the studio.');
  const worldHint=root.querySelector('.campus-camera-hint');
  worldHint.textContent='Drag to orbit · scroll to zoom · Enter for full screen';
  let worldOpen=false,worldEpoch=0,worldPreviousFocus=null,worldScroll=[0,0],worldOverflow='',worldInert=[];

  function restoreWorld(){
    if(!worldOpen)return;
    worldOpen=false;++worldEpoch;
    root.classList.remove('studio-world-open');layout.classList.remove('world-expanded');
    worldButton.textContent='Full screen ↗';worldButton.setAttribute('aria-expanded','false');
    worldHint.textContent='Drag to orbit · scroll to zoom · Enter for full screen';
    document.body.style.overflow=worldOverflow;
    worldInert.forEach(([node,value])=>node.inert=value);worldInert=[];
    if(worldPreviousFocus?.isConnected)worldPreviousFocus.focus({preventScroll:true});
    window.scrollTo(...worldScroll);
  }
  async function leaveWorld(){
    restoreWorld();
    if(document.fullscreenElement===root){try{await document.exitFullscreen();}catch{}}
  }
  async function enterWorld(){
    if(worldOpen||el('dialog').open)return;
    worldOpen=true;const epoch=++worldEpoch;
    worldPreviousFocus=document.activeElement;worldScroll=[window.scrollX,window.scrollY];worldOverflow=document.body.style.overflow;
    // The window-filling fallback has the same keyboard boundary as native fullscreen.
    for(let node=root;node.parentElement&&node!==document.body;node=node.parentElement){
      for(const sibling of node.parentElement.children){if(sibling!==node){worldInert.push([sibling,sibling.inert]);sibling.inert=true;}}
    }
    root.classList.add('studio-world-open');layout.classList.add('world-expanded');document.body.style.overflow='hidden';
    worldButton.textContent='Exit full screen · Esc';worldButton.setAttribute('aria-expanded','true');
    worldHint.textContent='Drag to orbit · scroll to zoom · Esc to return';
    worldViewport.focus({preventScroll:true});
    if(root.requestFullscreen&&!document.fullscreenElement){
      try{
        await root.requestFullscreen({navigationUI:'hide'});
        // An exit or view change can arrive while the browser is entering fullscreen.
        if(epoch!==worldEpoch&&document.fullscreenElement===root)await document.exitFullscreen();
      }catch{/* Keep the full-window experience when fullscreen is unavailable. */}
    }
  }
  worldButton.onclick=()=>worldOpen?leaveWorld():enterWorld();
  worldViewport.addEventListener('pointerdown',e=>{if(e.target.tagName==='CANVAS'||e.target===worldViewport)worldViewport.focus({preventScroll:true});});
  worldViewport.addEventListener('dblclick',e=>{
    if(el('dialog').open||e.target.closest('button'))return;
    e.preventDefault();if(!worldOpen)enterWorld();
  });
  worldViewport.addEventListener('keydown',e=>{
    if(e.target===worldViewport&&e.key==='Enter'&&!e.repeat){e.preventDefault();worldOpen?leaveWorld():enterWorld();}
  });
  document.addEventListener('keydown',e=>{if(e.key==='Escape'&&worldOpen&&!el('dialog').open){e.preventDefault();leaveWorld();}});
  document.addEventListener('fullscreenchange',()=>{if(document.fullscreenElement!==root)restoreWorld();});
  document.getElementById('bac-planner').addEventListener('bac:mode',e=>{if(e.detail!=='campus')leaveWorld();});
