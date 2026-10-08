  // Included in Studio's closure. Keep dialogs inside the fullscreen root.
  const worldViewport=document.getElementById('campus-viewport');
  const worldButton=document.createElement('button');
  worldButton.id='studio-focus';worldButton.type='button';
  worldButton.textContent='Full screen';worldButton.title='Full screen · Enter after selecting the 3D view';
  worldButton.setAttribute('aria-controls','campus-viewport');worldButton.setAttribute('aria-expanded','false');
  document.querySelector('.campus-scene-bottom .row').prepend(worldButton);
  worldViewport.tabIndex=0;worldViewport.setAttribute('role','region');
  worldViewport.setAttribute('aria-keyshortcuts','Enter');
  worldViewport.setAttribute('aria-label','Interactive 3D workshop. Click then press Enter for full screen, or double-click an empty area. Drag to orbit and scroll to zoom. Escape returns to the studio.');
  let worldOpen=false,worldEpoch=0,worldPreviousFocus=null,worldScroll=[0,0],worldOverflow='',worldInert=[];
  const resources=document.getElementById('studio-resources');
  document.addEventListener('pointerdown',e=>{if(!resources.contains(e.target))resources.open=false;});
  resources.addEventListener('focusout',e=>{if(!resources.contains(e.relatedTarget))resources.open=false;});
  resources.addEventListener('click',e=>{if(e.target.closest('a'))resources.open=false;});
  document.addEventListener('keydown',e=>{
    if(e.key==='Escape'&&resources.open){e.preventDefault();e.stopPropagation();resources.open=false;resources.querySelector('summary').focus();}
  },true);

  function restoreWorld(){
    if(!worldOpen)return;
    worldOpen=false;++worldEpoch;
    resources.open=false;
    document.querySelector('.studio-header-actions').append(resources,document.getElementById('studio-config'));
    root.classList.remove('studio-world-open');layout.classList.remove('world-expanded');
    worldButton.textContent='Full screen';worldButton.setAttribute('aria-expanded','false');
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
    resources.open=false;
    root.querySelector('.campus-scene-bottom .row').append(resources,document.getElementById('studio-config'));
    worldPreviousFocus=document.activeElement;worldScroll=[window.scrollX,window.scrollY];worldOverflow=document.body.style.overflow;
    // The window-filling fallback has the same keyboard boundary as native fullscreen.
    for(let node=root;node.parentElement&&node!==document.body;node=node.parentElement){
      for(const sibling of node.parentElement.children){if(sibling!==node){worldInert.push([sibling,sibling.inert]);sibling.inert=true;}}
    }
    root.classList.add('studio-world-open');layout.classList.add('world-expanded');document.body.style.overflow='hidden';
    worldButton.textContent='Exit full screen · Esc';worldButton.setAttribute('aria-expanded','true');
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
  document.addEventListener('keydown',e=>{if(e.key==='Escape'&&worldOpen&&!root.querySelector('dialog[open]')){e.preventDefault();leaveWorld();}});
  document.addEventListener('fullscreenchange',()=>{if(document.fullscreenElement!==root)restoreWorld();});
