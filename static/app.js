/* Lokaya_API frontend — talks to: GET /player-info, banner/avatar .webp, /refresh */
const $ = (id) => document.getElementById(id);
const state = { mediaUrl: null, bannerUrl: null, avatarUrl: null, uid: null, seq: 0 };
const HIST_KEY = 'lokaya_hist';

const REGIONS = { BD:'Bangladesh', SG:'Singapore', VN:'Vietnam', IND:'India', BR:'Brazil',
  US:'United States', NA:'North America', SAC:'South America', ID:'Indonesia', RU:'Russia',
  TW:'Taiwan', TH:'Thailand', ME:'Middle East', PK:'Pakistan', CIS:'Commonwealth', EUROPE:'Europe', EU:'Europe' };

const fmtInt = (v) => (v === undefined || v === null || v === '') ? '0' : Number(v).toLocaleString('en-US');
const fmtDateTime = (ts) => {
  if (!ts || ts === '0') return 'N/A';
  const d = new Date(Number(ts) * 1000);
  if (isNaN(d)) return ts;
  return d.toLocaleDateString('en-US', { month:'long', day:'numeric', year:'numeric' }) +
    ' at ' + d.toLocaleTimeString('en-US', { hour:'2-digit', minute:'2-digit', hour12:true });
};
const fmtDate = (ts) => {
  if (!ts || ts === '0') return 'N/A';
  const d = new Date(Number(ts) * 1000);
  return isNaN(d) ? ts : d.toLocaleDateString('en-US', { month:'long', day:'numeric', year:'numeric' });
};
const regionName = (c) => {
  if (!c) return '—';
  const n = REGIONS[String(c).toUpperCase()];
  return n ? `${n} (${String(c).toUpperCase()})` : c;
};
const cleanEnum = (v) => (!v ? 'N/A' : String(v).replace(/^(Gender|Language|ModePrefer|RankShow)_/, '').replace(/_/g, ' '));
const set = (id, v) => { const el = $(id); if (el) el.textContent = (v === undefined || v === null || v === '') ? 'N/A' : v; };

function showError(msg) {
  const e = $('err');
  e.textContent = msg;
  e.hidden = false;
  $('out').hidden = true;
  $('empty').style.display = 'block';
}
function clearError() { $('err').hidden = true; $('err').textContent = ''; }

async function loadBanner(url, seq) {
  const img = $('pBanner'), src = $('src');
  src.textContent = 'Loading official media…';
  try {
    const r = await fetch(url, { headers: { Accept: 'image/webp' } });
    if (!r.ok) throw new Error('HTTP ' + r.status);
    if (!(r.headers.get('content-type') || '').includes('image/webp')) throw new Error('not webp');
    const blob = await r.blob();
    if (seq !== state.seq) return;
    if (state.mediaUrl) URL.revokeObjectURL(state.mediaUrl);
    state.mediaUrl = URL.createObjectURL(blob);
    img.src = state.mediaUrl;
    const s = r.headers.get('x-free-fire-media-source') || '';
    src.textContent = s === 'official-free-fire-cdn'
      ? 'Official Free Fire CDN assets'
      : 'Official asset with local fallback';
  } catch {
    if (seq !== state.seq) return;
    src.textContent = 'Official asset unavailable · showing placeholder';
  }
}

async function search(uid) {
  uid = String(uid || '').trim();
  if (!/^\d+$/.test(uid)) return showError('Please enter a numeric UID.');
  const btn = $('go'), txt = $('goTxt');
  btn.disabled = true; txt.textContent = 'Loading…';
  clearError();
  const seq = ++state.seq;
  try {
    const r = await fetch('/player-info?uid=' + encodeURIComponent(uid));
    const d = await r.json();
    if (!r.ok || d.error) throw new Error(d.error || 'Lookup failed.');
    if (seq !== state.seq) return;

    const b = d.basicInfo || {}, s = d.socialInfo || {}, cr = d.creditScoreInfo || {},
          pet = d.petInfo || {}, clan = d.clanBasicInfo || {}, cap = d.captainBasicInfo || {},
          prof = d.profileInfo || {}, dia = d.diamondCostRes || {};
    const region = b.region || 'BD';

    set('pName', b.nickname || 'N/A');
    set('pLvl', b.level); $('pLikes').textContent = fmtInt(b.liked);
    set('pRegion', regionName(region)); set('pSince', fmtDate(b.createAt));
    set('pCredit', cr.creditScore);
    set('pDiamonds', dia.diamondCost !== undefined ? fmtInt(dia.diamondCost) : 'N/A');

    const bu = (d.mediaInfo && d.mediaInfo.bannerUrl) ||
      `/api/banner/banner_${encodeURIComponent(uid)}.webp?region=${encodeURIComponent(region)}`;
    const au = (d.mediaInfo && d.mediaInfo.avatarUrl) ||
      `/api/avatar/avatar_${encodeURIComponent(uid)}.webp?region=${encodeURIComponent(region)}`;
    state.bannerUrl = bu; state.avatarUrl = au; state.uid = uid;
    loadBanner(bu, seq);

    set('cUid', b.accountId || uid); set('cName', b.nickname);
    set('cLvl', b.level); set('cExp', b.exp !== undefined ? fmtInt(b.exp) : 'N/A');
    set('cRegion', regionName(region)); $('cLikes').textContent = fmtInt(b.liked);
    set('cGender', cleanEnum(s.gender)); set('cLanguage', cleanEnum(s.language));
    set('cMode', cleanEnum(s.modePrefer)); set('cBio', (s.signature || 'N/A'));

    $('rBr').textContent = fmtInt(b.rankingPoints);
    set('rBrRank', b.rank);
    set('rBrMax', b.maxRank); $('rCs').textContent = fmtInt(b.csRankingPoints);
    set('rCsRank', b.csRank); set('rCsMax', b.csMaxRank);
    set('rSeason', b.seasonId); set('rVer', b.releaseVersion); set('rCreated', fmtDateTime(b.createAt)); set('rLogin', fmtDateTime(b.lastLoginAt));

    set('lAvatar', b.headPic); set('lBanner', b.bannerId);
    set('lChar', prof.avatarId); set('lAwake', prof.isSelectedAwaken ? 'Yes' : 'No');
    set('lClothes', Array.isArray(prof.clothes) ? prof.clothes.length + ' items' : 'N/A');
    set('lSkills', Array.isArray(prof.equipedSkills) ? Math.floor(prof.equipedSkills.length / 4) + ' equipped' : 'N/A');
    set('lBadges', b.badgeCnt); set('lTitle', b.title); set('lPin', b.pinId);

    set('tId', pet.id); set('tLvl', pet.level);
    set('tExp', pet.exp !== undefined ? fmtInt(pet.exp) : 'N/A');
    set('tSel', pet.isSelected ? 'Yes' : 'No');
    set('tSkill', pet.selectedSkillId); set('tSkin', pet.skinId);

    set('gName', clan.clanName); set('gId', clan.clanId);
    set('gLvl', clan.clanLevel);
    set('gMem', clan.capacity ? `${clan.memberNum || 0}/${clan.capacity}` : 'N/A');
    $('gLeader').textContent = (cap && cap.nickname)
      ? `Leader: ${cap.nickname} · UID ${cap.accountId || 'N/A'} · Lv ${cap.level || 'N/A'} · ${fmtInt(cap.liked)} likes`
      : 'No guild leader info';

    $('rawBody').textContent = JSON.stringify(d, null, 2);
    $('raw').hidden = true;
    pushHistory(uid);

    $('empty').style.display = 'none';
    $('out').hidden = false;
  } catch (e) {
    if (seq !== state.seq) return;
    showError(e.message);
  } finally {
    btn.disabled = false; txt.textContent = 'Search';
  }
}

function reset() {
  state.seq++;
  if (state.mediaUrl) { URL.revokeObjectURL(state.mediaUrl); state.mediaUrl = null; }
  state.bannerUrl = state.avatarUrl = state.uid = null;
  $('uid').value = ''; $('pBanner').removeAttribute('src');
  $('out').hidden = true; $('raw').hidden = true;
  clearError(); $('empty').style.display = 'block';
  $('uid').focus();
}

async function downloadMedia(kind) {
  const url = kind === 'avatar' ? state.avatarUrl : (state.mediaUrl || state.bannerUrl);
  if (!url) return;
  const name = `${kind}_${state.uid || 'player'}.webp`;
  try {
    const r = await fetch(url);
    if (!r.ok) throw new Error('fetch failed');
    const blob = await r.blob();
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = name;
    document.body.appendChild(a);
    a.click();
    setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 4000);
  } catch {
    window.open(url, '_blank');
  }
}

function getHistory() {
  try { return JSON.parse(localStorage.getItem(HIST_KEY) || '[]'); }
  catch { return []; }
}
function pushHistory(uid) {
  const h = [uid, ...getHistory().filter((x) => x !== uid)].slice(0, 8);
  try { localStorage.setItem(HIST_KEY, JSON.stringify(h)); } catch {}
  renderHistory();
}
function renderHistory() {
  const h = getHistory(), box = $('hist'), chips = $('histChips');
  chips.innerHTML = '';
  if (!h.length) { box.hidden = true; return; }
  box.hidden = false;
  h.forEach((u) => {
    const b = document.createElement('button');
    b.type = 'button'; b.textContent = u;
    b.addEventListener('click', () => { $('uid').value = u; search(u); });
    chips.appendChild(b);
  });
}

document.addEventListener('DOMContentLoaded', () => {
  $('frm').addEventListener('submit', (e) => { e.preventDefault(); search($('uid').value); });
  $('again').addEventListener('click', reset);
  $('dlBanner').addEventListener('click', () => downloadMedia('banner'));
  $('dlAvatar').addEventListener('click', () => downloadMedia('avatar'));
  $('rawToggle').addEventListener('click', () => { $('raw').hidden = !$('raw').hidden; });
  $('histClear').addEventListener('click', () => {
    try { localStorage.removeItem(HIST_KEY); } catch {}
    renderHistory();
  });
  renderHistory();
  $('rawCopy').addEventListener('click', async () => {
    const txt = $('rawBody').textContent || '{}';
    const label = $('rawCopyTxt');
    try {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(txt);
      } else {
        const ta = document.createElement('textarea');
        ta.value = txt;
        document.body.appendChild(ta);
        ta.select();
        document.execCommand('copy');
        ta.remove();
      }
      label.textContent = 'Copied!';
    } catch {
      label.textContent = 'Copy failed';
    }
    setTimeout(() => { label.textContent = 'Copy JSON'; }, 1500);
  });
});
