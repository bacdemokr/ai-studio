// Presenter aids are local drafts. Selecting an example never starts a task.
window.BacOverviewImages={agent:'__AGENT_BIG_PICTURE_DATA_URL__',openshell:'__OPENSHELL_OVERVIEW_DATA_URL__'};
const agentBlueprint=`<div class="agent-blueprint" aria-label="에이전트는 언어 모델, 지침, 스킬, 기억을 도구 실행환경과 함께 사용합니다">
 <div class="agent-blueprint-input">사용자의 요청 <span>또는 주기적인 Heartbeat</span></div><span class="agent-blueprint-arrow" aria-hidden="true">↓</span>
 <section class="agent-blueprint-runtime"><header>에이전트 실행환경 <small>OpenClaw가 실행 과정을 연결합니다</small></header>
 <div class="agent-blueprint-parts"><article><b>역할과 말투</b><span>목적과 행동 방식</span></article><article><b>언어 모델</b><span>판단하고 행동 선택</span></article><article><b>스킬</b><span>특정 작업을 위한 지침</span></article><article><b>기억과 파일</b><span>저장된 맥락과 근거</span></article></div>
 <div class="agent-blueprint-tools"><b>허용된 도구</b><span>읽기, 쓰기, 검색, 자료 가져오기</span><small>도구 결과 확인 → 다음 행동 판단 → 준비되면 답변</small><small>OpenShell로 도구 실행을 격리하고 접근을 제한할 수 있습니다.</small></div></section>
 <span class="agent-blueprint-arrow" aria-hidden="true">↓</span><div class="agent-blueprint-output">답변 또는 저장된 결과 <span>근거를 확인해주세요. 항상 성공하는 것은 아닙니다.</span></div></div>`;
window.BacAgentBlueprint=agentBlueprint;
el('crew-goal-intro').textContent='원하는 작업을 알려주세요. Casey가 알맞은 팀을 구성하고 결과를 모아줍니다.';
function goalHint(choice){return choice.detail;}
function goalPrompt(choice){return choice.prompt.replaceAll('{{city}}',()=>runtime.location?.city||'Seoul');}
el('crew-goal-choices').innerHTML='<div class="studio-goal-options">'+goalExamples.map(g=>`<button type="button" data-goal-example="${escape(g.id)}" data-goal-hint="${escape(goalHint(g))}" aria-pressed="false" title="${escape(goalHint(g))}" aria-controls="studio-crew-prompt">${escape(g.title)}</button>`).join('')+'</div>';
function syncGoalExamples(locked){
 const box=el('crew-examples');box.hidden=locked||selectedScenario!=='plan'||selectedCrewRole!==0||!!selectedOpenTaskVisitor;
 box.querySelectorAll('[data-goal-example]').forEach(button=>{
  const choice=goalExamples.find(g=>g.id===button.dataset.goalExample);
  button.disabled=locked||box.hidden;
  button.setAttribute('aria-pressed',String(el('crew-prompt').value===goalPrompt(choice)));
  button.dataset.goalHint=goalHint(choice);
  button.title=goalHint(choice);
 });
}
el('crew-goal-choices').onclick=event=>{
 const button=event.target.closest('[data-goal-example]');
 if(!button||button.disabled||selectedCrewRole!==0||selectedOpenTaskVisitor||selectedScenario!=='plan')return;
 syncCrewComposer();if(button.disabled)return;
 const choice=goalExamples.find(g=>g.id===button.dataset.goalExample),prompt=el('crew-prompt');
 el('crew-chat-error').hidden=true;
 const selection=crewDocumentSelection();
 selection.example=choice.document?'inbox/'+choice.document:'';
 selection.lockedExample=choice.requiredDocument?selection.example:'';
 if(selection.example)selection.excluded.delete(selection.example);
 prompt.value=goalPrompt(choice);prompt.dispatchEvent(new Event('input',{bubbles:true}));
 prompt.focus({preventScroll:true});prompt.setSelectionRange(prompt.value.length,prompt.value.length);prompt.scrollTop=0;
};
function issueReportPanel(){return `<details id="studio-issue-report" class="studio-issue-report"><summary>Issue report</summary><div id="studio-issue-report-content">
 <header class="studio-issue-heading"><div><h3>AI Studio <span class="studio-issue-version">v${escape(buildInfo.version)}</span></h3></div></header>
 <dl class="studio-issue-details"><div><dt>Branch</dt><dd>${escape(buildInfo.branch||'Packaged build')}</dd></div><div><dt>Source commit</dt><dd><code>${escape(buildInfo.commit?.slice(0,12)||'Not recorded')}</code>${buildInfo.modified?'<span class="studio-issue-local">Local changes</span>':''}</dd></div></dl>
 <section class="studio-issue-runtime" aria-label="Pinned runtime versions"><h4>Pinned runtime</h4><dl>${Object.entries(buildInfo.runtime||{}).map(([key,value])=>`<div><dt>${escape(({node:'Node.js',openclaw:'OpenClaw',openshell:'OpenShell'})[key]||key)}</dt><dd>${escape(value)}</dd></div>`).join('')}</dl></section>
 <footer class="studio-issue-footer"><p>Build info and recent diagnostics.<br>No chat or file contents.</p><div class="studio-diagnostic-actions"><button type="button" class="studio-secondary" id="studio-copy-build">Copy diagnostics</button><button type="button" id="studio-download-diagnostics">Download</button></div></footer><p id="studio-build-copy-status" role="status"></p>
 </div></details>`;}
