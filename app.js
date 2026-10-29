const SOURCE='https://spb.ranepa.ru/raspisanie/ekonomicheskaya-bezopasnost-eb-5-23-01-eb-5-23-02/';
const MONTHS=['января','февраля','марта','апреля','мая','июня','июля','августа','сентября','октября','ноября','декабря'];
const MONTHS_N=['январь','февраль','март','апрель','май','июнь','июль','август','сентябрь','октябрь','ноябрь','декабрь'];
const WD=['Вс','Пн','Вт','Ср','Чт','Пт','Сб'];
let data={events:[],meta:{},history:[]}, view='week', cursor=new Date(); cursor.setHours(0,0,0,0);
const $=s=>document.querySelector(s);
const dateKey=d=>`${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
const parseDate=s=>{const [y,m,d]=s.split('-').map(Number);return new Date(y,m-1,d)};
const fmtDate=d=>`${d.getDate()} ${MONTHS[d.getMonth()]} ${d.getFullYear()}`;
function sameDay(a,b){return dateKey(a)===dateKey(b)}
function shownEvents(){const g=$('#group').value;return data.events.filter(e=>g==='all'||(e.groups||'').includes(g)).sort((a,b)=>(a.date+a.start).localeCompare(b.date+b.start))}
function setStatus(){
 const m=data.meta||{};
 $('#checkedAt').textContent=m.last_checked?`Проверено: ${new Date(m.last_checked).toLocaleString('ru-RU',{timeZone:'Europe/Moscow'})} (МСК)`:'Пока не было успешной проверки';
 $('#statusText').textContent = m.error
  ? (m.check_summary || 'Проверка расписания — Ошибка проверки')
  : (m.check_summary || (m.last_checked
      ? 'Источник проверен'
      : 'Ожидается первая проверка'));
 $('#changeText').textContent=m.last_changed?`${new Date(m.last_changed).toLocaleString('ru-RU',{timeZone:'Europe/Moscow'})} (МСК). ${m.change_summary||'Обнаружено изменение расписания.'}`:'Изменения пока не зафиксированы. Дата появится после первого отличия от предыдущей версии.';
 const hist=data.history||[];
 $('#historyList').innerHTML=hist.length?hist.slice(0,8).map(h=>`<div class="historyitem"><span class="tag">${esc(h.kind||'обновление')}</span><b>${esc(h.date?new Date(h.date).toLocaleString('ru-RU',{timeZone:'Europe/Moscow'}):'Дата неизвестна')}</b><p>${esc(h.summary||'Расписание проверено.')}</p></div>`).join(''):'<div class="historyitem"><b>История пока пуста</b><p>Когда GitHub Actions обнаружит первое изменение, оно появится здесь.</p></div>';
}
function esc(s){return String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
function eventHtml(e){let cls=e.type==='Пр'?'practice':(e.type==='ДСР'?'other':'');return `<div class="event ${cls}"><div class="time">${esc(e.start||'Время не указано')}${e.end?'–'+esc(e.end):''}</div><div class="subject">${esc(e.subject)}</div><div class="detail">${esc(e.type||'Занятие')} · ${esc(e.teacher||'Преподаватель не указан')}<br>Ауд. ${esc(e.room||'не указана')}<br>${esc(e.groups||'')}</div></div>`}
function render(){
 setStatus(); const events=shownEvents(); const cal=$('#calendar');
 if(!events.length){$('#periodTitle').textContent='Нет данных';cal.innerHTML=`<div class="empty">Расписание пока не загружено. Проверьте вкладку Actions в GitHub или откройте <a style="color:#7cb4ff" href="${SOURCE}" target="_blank">расписание на сайте вуза</a>.</div>`;return}
 if(view==='week') renderWeek(cal,events); else if(view==='month') renderMonth(cal,events); else renderList(cal,events);
}
function renderWeek(cal,events){
 const start=new Date(cursor);start.setDate(start.getDate()-(start.getDay()+6)%7);const end=new Date(start);end.setDate(end.getDate()+6);
 $('#periodTitle').textContent=`${start.getDate()} ${MONTHS[start.getMonth()]} — ${end.getDate()} ${MONTHS[end.getMonth()]} ${end.getFullYear()}`;
 cal.innerHTML=`<div class="weekgrid">${Array.from({length:7},(_,i)=>{let d=new Date(start);d.setDate(start.getDate()+i);let list=events.filter(e=>e.date===dateKey(d));return `<div class="daycol"><div class="dayhead ${sameDay(d,new Date())?'todayhead':''}">${WD[d.getDay()]}<b>${d.getDate()}</b></div><div class="events">${list.length?list.map(eventHtml).join(''):'<div class="muted" style="text-align:center;font-size:10px;padding:15px 0">—</div>'}</div></div>`}).join('')}</div>`;
}
function renderMonth(cal,events){
 $('#periodTitle').textContent=`${MONTHS_N[cursor.getMonth()]} ${cursor.getFullYear()}`;
 const first=new Date(cursor.getFullYear(),cursor.getMonth(),1), offset=(first.getDay()+6)%7, start=new Date(first);start.setDate(1-offset);
 let html=WD.slice(1).concat(WD[0]).map(x=>`<div class="monthlabel">${x}</div>`).join('');
 for(let i=0;i<42;i++){let d=new Date(start);d.setDate(start.getDate()+i);let list=events.filter(e=>e.date===dateKey(d));html+=`<div class="monthcell ${d.getMonth()!==cursor.getMonth()?'dim':''}"><div class="monthnum ${sameDay(d,new Date())?'todaynum':''}">${d.getDate()}</div>${list.slice(0,3).map(e=>`<div class="minievent">${esc(e.start)} ${esc(e.subject)}</div>`).join('')}${list.length>3?`<div class="minievent">+ ещё ${list.length-3}</div>`:''}</div>`}
 cal.innerHTML=`<div class="monthgrid">${html}</div>`;
}
function renderList(cal,events){
 const grouped={};events.forEach(e=>(grouped[e.date]??=[]).push(e));const keys=Object.keys(grouped).sort();const rangeStart=new Date(cursor);rangeStart.setDate(rangeStart.getDate()-(rangeStart.getDay()+6)%7);const rangeEnd=new Date(rangeStart);rangeEnd.setDate(rangeEnd.getDate()+6);
 const visible=keys.filter(k=>parseDate(k)>=rangeStart&&parseDate(k)<=rangeEnd);
 $('#periodTitle').textContent=`Список · ${fmtDate(rangeStart)} — ${fmtDate(rangeEnd)}`;
 cal.innerHTML=visible.length?visible.map(k=>`<div class="listday"><h3>${WD[parseDate(k).getDay()]}, ${fmtDate(parseDate(k))}</h3>${grouped[k].map(eventHtml).join('')}</div>`).join(''):'<div class="empty">На этой неделе пар не найдено.</div>';
}
function move(n){if(view==='month')cursor.setMonth(cursor.getMonth()+n);else cursor.setDate(cursor.getDate()+7*n);render()}
function exportICS(){
 const events=shownEvents().filter(e=>e.start&&e.end&&e.start.includes(':')&&e.end.includes(':'));
 if(!events.length){alert('Нет событий с корректным временем для экспорта.');return}
 const stamp=d=>d.toISOString().replace(/[-:]/g,'').replace(/\.\d{3}/,'');
 const lines=['BEGIN:VCALENDAR','VERSION:2.0','PRODID:-//Schedule Monitor//RU','CALSCALE:GREGORIAN','METHOD:PUBLISH'];
 events.forEach(e=>{const dt=e.date.replaceAll('-','');const [sh,sm]=e.start.split(':');const [eh,em]=e.end.split(':');const desc=`Преподаватель: ${e.teacher||'не указан'}\\nАудитория: ${e.room||'не указана'}\\nГруппа: ${e.groups||''}`;
 lines.push('BEGIN:VEVENT',`UID:${dt}-${sh}${sm}-${encodeURIComponent(e.subject)}@schedule-monitor`,`DTSTAMP:${stamp(new Date())}`,`DTSTART;TZID=Europe/Moscow:${dt}T${sh}${sm}00`,`DTEND;TZID=Europe/Moscow:${dt}T${eh}${em}00`,`SUMMARY:${icsEscape(e.subject)}`,`LOCATION:${icsEscape(e.room||'')}`,`DESCRIPTION:${icsEscape(desc)}`,'END:VEVENT')});
 lines.push('END:VCALENDAR');const blob=new Blob([lines.join('\r\n')],{type:'text/calendar;charset=utf-8'});const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='ranepa-schedule.ics';a.click();URL.revokeObjectURL(a.href);
}
function icsEscape(s){return String(s).replace(/\\/g,'\\\\').replace(/,/g,'\\,').replace(/;/g,'\\;').replace(/\n/g,'\\n')}
document.querySelectorAll('.view').forEach(b=>b.addEventListener('click',()=>{view=b.dataset.view;document.querySelectorAll('.view').forEach(x=>x.classList.toggle('active',x===b));render()}));
$('#prev').onclick=()=>move(-1);$('#next').onclick=()=>move(1);$('#today').onclick=()=>{cursor=new Date();cursor.setHours(0,0,0,0);render()};$('#group').onchange=render;$('#ics').onclick=exportICS;$('#refreshBtn').onclick=()=>loadData(true);
async function loadData(force=false){try{const bust=force?'?t='+Date.now():'';const r=await fetch('data/schedule.json'+bust,{cache:'no-store'});if(!r.ok)throw Error('schedule.json not found');data=await r.json();render()}catch(e){data={events:[],meta:{error:true},history:[]};render()}}
loadData();