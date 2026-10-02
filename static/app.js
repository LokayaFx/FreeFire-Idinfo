let mediaRequestSequence = 0;

function quickFill(uid) {
    document.getElementById('uid-input').value = uid;
    document.getElementById('search-form').requestSubmit();
}

function renderLocalNativeBanner(basic, clan) {
    const canvas = document.createElement('canvas');
    canvas.width = 800;
    canvas.height = 220;
    const ctx = canvas.getContext('2d');

    const nickname = basic.nickname || 'N/A';
    const guild = clan.clanName || 'NO GUILD';
    const level = basic.level || '0';
    const region = basic.region || 'BD';
    const bannerId = basic.bannerId || '901000116';

    // 1. Pure Canvas Dynamic Gradient Background
    let grad = ctx.createLinearGradient(0, 0, 800, 220);
    const themeIndex = Math.abs(parseInt(bannerId, 10) || 0) % 5;
    if (themeIndex === 0) {
        grad.addColorStop(0, '#881337');
        grad.addColorStop(0.5, '#dc2626');
        grad.addColorStop(1, '#1e1b4b');
    } else if (themeIndex === 1) {
        grad.addColorStop(0, '#78350f');
        grad.addColorStop(0.5, '#d97706');
        grad.addColorStop(1, '#451a03');
    } else if (themeIndex === 2) {
        grad.addColorStop(0, '#4c1d95');
        grad.addColorStop(0.5, '#7c3aed');
        grad.addColorStop(1, '#2e1065');
    } else if (themeIndex === 3) {
        grad.addColorStop(0, '#0c4a6e');
        grad.addColorStop(0.5, '#0284c7');
        grad.addColorStop(1, '#082f49');
    } else {
        grad.addColorStop(0, '#064e3b');
        grad.addColorStop(0.5, '#059669');
        grad.addColorStop(1, '#022c22');
    }
    ctx.fillStyle = grad;
    ctx.fillRect(0, 0, 800, 220);

    // 2. Diagonal Gaming Speed Lines
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.07)';
    ctx.lineWidth = 14;
    for (let x = -200; x < 1000; x += 40) {
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x + 180, 220);
        ctx.stroke();
    }

    // 3. Gold Accent Outer Frame
    ctx.strokeStyle = 'rgba(245, 158, 11, 0.6)';
    ctx.lineWidth = 4;
    ctx.strokeRect(2, 2, 796, 216);

    // 4. Self-Contained Vector Avatar Frame
    const avX = 20, avY = 20, avSize = 180;
    ctx.fillStyle = '#0f172a';
    ctx.fillRect(avX, avY, avSize, avSize);
    ctx.strokeStyle = '#f59e0b';
    ctx.lineWidth = 3;
    ctx.strokeRect(avX, avY, avSize, avSize);

    // Pure Vector Avatar Silhouette
    ctx.save();
    ctx.translate(avX + avSize / 2, avY + avSize / 2);
    ctx.fillStyle = '#38bdf8';
    ctx.beginPath();
    ctx.arc(0, -20, 34, 0, Math.PI * 2);
    ctx.fill();
    ctx.beginPath();
    ctx.arc(0, 50, 55, Math.PI, 0, false);
    ctx.fill();
    ctx.restore();

    // 5. Dynamic Player Text Overlays
    ctx.textAlign = 'left';
    ctx.fillStyle = '#ffffff';
    ctx.font = '900 36px "Outfit", sans-serif';
    ctx.shadowColor = 'rgba(0, 0, 0, 0.9)';
    ctx.shadowBlur = 8;
    ctx.shadowOffsetX = 3;
    ctx.shadowOffsetY = 3;
    ctx.fillText(nickname, 230, 85);

    ctx.font = '700 22px "Outfit", sans-serif';
    ctx.fillStyle = '#f1f5f9';
    ctx.fillText(`Guild: ${guild}`, 230, 135);

    ctx.font = '600 18px "Outfit", sans-serif';
    ctx.fillStyle = '#fbbf24';
    ctx.fillText(`Region: ${region}`, 230, 170);

    // Level Badge
    ctx.textAlign = 'right';
    ctx.font = '900 32px "Outfit", sans-serif';
    ctx.fillStyle = '#ffffff';
    ctx.fillText(`Lvl. ${level}`, 770, 170);

    const bannerDataUrl = canvas.toDataURL('image/png');
    const realBannerEl = document.getElementById('real-banner-img');
    if (realBannerEl) {
        realBannerEl.src = bannerDataUrl;
    }
    return bannerDataUrl;
}

async function renderDynamicPlayerBanner(data, basic, clan, uid, region) {
    const requestSequence = ++mediaRequestSequence;
    const bannerEl = document.getElementById('real-banner-img');
    const statusEl = document.getElementById('media-source-status');
    if (!bannerEl) return;

    const suppliedUrl = data.mediaInfo && data.mediaInfo.bannerUrl;
    const version = `${basic.bannerId || 0}-${basic.headPic || 0}`;
    const bannerUrl = suppliedUrl || `/api/banner/banner_${encodeURIComponent(uid)}.webp?region=${encodeURIComponent(region)}&v=${encodeURIComponent(version)}`;

    if (statusEl) {
        statusEl.className = 'media-source-status is-loading';
        statusEl.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i> Loading official Free Fire media…';
    }
    bannerEl.classList.add('is-loading');

    try {
        const response = await fetch(bannerUrl, {
            headers: { 'Accept': 'image/webp' },
            cache: 'force-cache'
        });
        if (!response.ok) {
            throw new Error(`Banner endpoint returned HTTP ${response.status}`);
        }
        const contentType = response.headers.get('content-type') || '';
        if (!contentType.includes('image/webp')) {
            throw new Error('Banner endpoint did not return a WebP image.');
        }

        const source = response.headers.get('x-free-fire-media-source') || 'official-or-local';
        const blob = await response.blob();
        if (requestSequence !== mediaRequestSequence) return;
        if (bannerEl.dataset.objectUrl) {
            URL.revokeObjectURL(bannerEl.dataset.objectUrl);
        }
        const objectUrl = URL.createObjectURL(blob);
        bannerEl.dataset.objectUrl = objectUrl;
        bannerEl.src = objectUrl;
        bannerEl.classList.remove('is-loading');

        if (statusEl) {
            if (source === 'official-free-fire-cdn') {
                statusEl.className = 'media-source-status is-official';
                statusEl.innerHTML = '<i class="fa-solid fa-shield-halved"></i> Official Free Fire CDN assets · served locally';
            } else if (source.includes('official-free-fire-cdn')) {
                statusEl.className = 'media-source-status is-mixed';
                statusEl.innerHTML = '<i class="fa-solid fa-shield-halved"></i> Official Free Fire asset with local fallback';
            } else {
                statusEl.className = 'media-source-status is-fallback';
                statusEl.innerHTML = '<i class="fa-solid fa-image"></i> Official asset unavailable · safe local fallback';
            }
        }
    } catch (error) {
        if (requestSequence !== mediaRequestSequence) return;
        console.warn('Official player media could not be loaded:', error);
        bannerEl.classList.remove('is-loading');
        renderLocalNativeBanner(basic, clan);
        if (statusEl) {
            statusEl.className = 'media-source-status is-fallback';
            statusEl.innerHTML = '<i class="fa-solid fa-image"></i> Official asset unavailable · browser fallback';
        }
    }
}

function resetSearch() {
    mediaRequestSequence += 1;
    document.getElementById('uid-input').value = '';
    document.getElementById('results-wrapper').style.display = 'none';
    document.getElementById('initial-placeholder').style.display = 'block';
    document.getElementById('error-banner').style.display = 'none';

    const bannerEl = document.getElementById('real-banner-img');
    if (bannerEl) {
        if (bannerEl.dataset.objectUrl) {
            URL.revokeObjectURL(bannerEl.dataset.objectUrl);
            delete bannerEl.dataset.objectUrl;
        }
        bannerEl.removeAttribute('src');
        bannerEl.classList.remove('is-loading');
    }
    const statusEl = document.getElementById('media-source-status');
    if (statusEl) {
        statusEl.className = 'media-source-status';
        statusEl.innerHTML = '<i class="fa-solid fa-shield-halved"></i> Official Free Fire media loads after lookup';
    }
}

function formatFullDateTime(timestamp) {
    if (!timestamp || timestamp === '0' || timestamp === '--') return 'N/A';
    const num = parseInt(timestamp, 10);
    if (isNaN(num)) return timestamp;
    const date = new Date(num * 1000);
    
    const dateStr = date.toLocaleDateString('en-US', {
        month: 'long',
        day: 'numeric',
        year: 'numeric'
    });
    
    const timeStr = date.toLocaleTimeString('en-US', {
        hour: '2-digit',
        minute: '2-digit',
        hour12: true
    });
    
    return `${dateStr} at ${timeStr}`;
}

function formatFullDateOnly(timestamp) {
    if (!timestamp || timestamp === '0' || timestamp === '--') return 'N/A';
    const num = parseInt(timestamp, 10);
    if (isNaN(num)) return timestamp;
    const date = new Date(num * 1000);
    return date.toLocaleDateString('en-US', {
        month: 'long',
        day: 'numeric',
        year: 'numeric'
    });
}

function formatNumber(num) {
    if (num === undefined || num === null) return '0';
    return Number(num).toLocaleString('en-US');
}

const REGION_NAMES = {
    'BD': 'Bangladesh',
    'SG': 'Singapore',
    'VN': 'Vietnam',
    'IND': 'India',
    'BR': 'Brazil',
    'US': 'United States',
    'NA': 'North America',
    'SAC': 'South America',
    'ID': 'Indonesia',
    'RU': 'Russia',
    'TW': 'Taiwan',
    'TH': 'Thailand',
    'ME': 'Middle East',
    'PK': 'Pakistan',
    'CIS': 'Commonwealth',
    'EUROPE': 'Europe',
    'EU': 'Europe'
};

function formatRegionName(regionCode) {
    if (!regionCode) return '--';
    const code = String(regionCode).toUpperCase();
    const name = REGION_NAMES[code];
    return name ? `${name} (${code})` : code;
}

function formatEnumText(val) {
    if (!val) return 'N/A';
    return String(val)
        .replace(/^Gender_/, '')
        .replace(/^Language_/, '')
        .replace(/^ModePrefer_/, '')
        .replace(/^RankShow_/, '')
        .replace(/_/g, ' ');
}

function toggleRawJson() {
    const body = document.getElementById('json-body');
    const arrow = document.getElementById('json-arrow');
    if (body.style.display === 'none') {
        body.style.display = 'block';
        arrow.className = 'fa-solid fa-chevron-up';
    } else {
        body.style.display = 'none';
        arrow.className = 'fa-solid fa-chevron-down';
    }
}

async function handleSearch(event) {
    event.preventDefault();

    const uid = document.getElementById('uid-input').value.trim();
    const btnText = document.querySelector('.btn-text');
    const btnSpinner = document.querySelector('.btn-spinner');
    const errorBanner = document.getElementById('error-banner');
    const placeholder = document.getElementById('initial-placeholder');
    const results = document.getElementById('results-wrapper');

    if (!uid) return;

    btnText.style.display = 'none';
    btnSpinner.style.display = 'inline-block';
    errorBanner.style.display = 'none';

    try {
        const response = await fetch(`/player-info?uid=${encodeURIComponent(uid)}`);
        const data = await response.json();

        if (!response.ok || data.error) {
            const errorMessages = {
                PLAYER_NOT_FOUND: 'Player not found in the available regions.',
                LOOKUP_INCOMPLETE: 'Some regions are temporarily unavailable. Try selecting a region or retry later.',
                GUEST_AUTH_FAILED: 'The service account could not authenticate. Check its credentials.',
                UNRECOGNIZED_LOGIN_RESPONSE: 'The service account login did not return a usable token. Check the account and OB protocol.',
                CREDENTIAL_CONFIG_ERROR: 'A service account is missing or misconfigured. Check the account configuration.',
                UPSTREAM_HTTP_ERROR: 'The Free Fire service returned an error. Retry later or check the OB update guide.',
                UPSTREAM_CONNECTION_ERROR: 'Could not reach the Free Fire service. Retry later.'
            };
            throw new Error(errorMessages[data.code] || data.error || 'Failed to fetch player data from Free Fire official server.');
        }

        const basic = data.basicInfo || {};
        const social = data.socialInfo || {};
        const credit = data.creditScoreInfo || {};
        const pet = data.petInfo || {};
        const clan = data.clanBasicInfo || {};
        const captain = data.captainBasicInfo || {};
        const profile = data.profileInfo || {};
        const diamonds = data.diamondCostRes || {};

        const playerRegion = basic.region || 'BD';
        const fullRegionName = formatRegionName(playerRegion);

        // Top Summary Header
        const hdrNicknameEl = document.getElementById('hdr-nickname');
        const hdrLevelEl = document.getElementById('hdr-level');
        const hdrLikesEl = document.getElementById('hdr-likes');
        const hdrRegionEl = document.getElementById('hdr-region');
        const hdrIdOpenEl = document.getElementById('hdr-id-open');

        if (hdrNicknameEl) hdrNicknameEl.textContent = basic.nickname || 'N/A';
        if (hdrLevelEl) hdrLevelEl.textContent = basic.level || '--';
        if (hdrLikesEl) hdrLikesEl.textContent = formatNumber(basic.liked);
        if (hdrRegionEl) hdrRegionEl.textContent = fullRegionName;
        if (hdrIdOpenEl) hdrIdOpenEl.textContent = formatFullDateOnly(basic.createAt);

        // Load the locally served banner made from official Free Fire item assets.
        // The existing canvas renderer remains as the final no-network fallback.
        void renderDynamicPlayerBanner(data, basic, clan, uid, playerRegion);

        // 1. ACCOUNT INFO
        document.getElementById('val-uid').textContent = basic.accountId || uid;
        document.getElementById('val-name').textContent = basic.nickname || 'N/A';
        document.getElementById('val-level').textContent = basic.level || '0';
        if (document.getElementById('val-exp')) document.getElementById('val-exp').textContent = basic.exp ? formatNumber(basic.exp) : '0';
        document.getElementById('val-region').textContent = fullRegionName;
        document.getElementById('val-likes').textContent = formatNumber(basic.liked);
        if (document.getElementById('val-gender')) document.getElementById('val-gender').textContent = formatEnumText(social.gender);
        if (document.getElementById('val-language')) document.getElementById('val-language').textContent = formatEnumText(social.language);
        if (document.getElementById('val-mode-pref')) document.getElementById('val-mode-pref').textContent = formatEnumText(social.modePrefer);
        document.getElementById('val-season').textContent = basic.seasonId || 'N/A';
        document.getElementById('val-credit').textContent = credit.creditScore ? `${credit.creditScore}` : '100';
        if (document.getElementById('val-pin-id')) document.getElementById('val-pin-id').textContent = basic.pinId || 'N/A';
        document.getElementById('val-title').textContent = basic.title || 'N/A';
        document.getElementById('val-bio').textContent = social.signature || 'N/A';

        // 2. ACCOUNT ACTIVITY
        document.getElementById('val-rel-ver').textContent = basic.releaseVersion || 'Unknown';
        document.getElementById('val-br-pts').textContent = formatNumber(basic.rankingPoints);
        document.getElementById('val-br-max').textContent = basic.maxRank ? `${basic.maxRank}` : 'N/A';
        document.getElementById('val-cs-pts').textContent = formatNumber(basic.csRankingPoints);
        document.getElementById('val-cs-rank').textContent = basic.csRank ? `${basic.csRank}` : 'N/A';
        document.getElementById('val-cs-max').textContent = basic.csMaxRank ? `${basic.csMaxRank}` : 'N/A';
        if (document.getElementById('val-diamonds')) document.getElementById('val-diamonds').textContent = diamonds.diamondCost !== undefined ? `${formatNumber(diamonds.diamondCost)} Diamonds` : 'N/A';
        if (document.getElementById('val-rank-show')) document.getElementById('val-rank-show').textContent = formatEnumText(social.rankShow);
        document.getElementById('val-created-at').textContent = formatFullDateTime(basic.createAt);
        document.getElementById('val-last-login').textContent = formatFullDateTime(basic.lastLoginAt);

        // 3. ACCOUNT OVERVIEW
        document.getElementById('val-avatar-id').textContent = basic.headPic || 'N/A';
        document.getElementById('val-banner-id').textContent = basic.bannerId || 'N/A';
        if (document.getElementById('val-char-id')) document.getElementById('val-char-id').textContent = profile.avatarId || 'N/A';
        if (document.getElementById('val-char-awaken')) document.getElementById('val-char-awaken').textContent = profile.isSelectedAwaken ? 'Yes' : 'No';
        if (document.getElementById('val-clothes-cnt')) document.getElementById('val-clothes-cnt').textContent = Array.isArray(profile.clothes) ? `${profile.clothes.length} items` : 'N/A';
        if (document.getElementById('val-skills-cnt')) document.getElementById('val-skills-cnt').textContent = Array.isArray(profile.equipedSkills) ? `${Math.floor(profile.equipedSkills.length / 4)} equipped` : 'N/A';
        document.getElementById('val-bp-badges').textContent = basic.badgeCnt || '0';
        document.getElementById('val-bp-id').textContent = basic.badgeId || 'N/A';
        document.getElementById('val-acc-type').textContent = basic.accountType !== undefined ? basic.accountType : '1';
        document.getElementById('val-show-br').textContent = basic.showBrRank ? 'Yes' : 'No';
        document.getElementById('val-show-cs').textContent = basic.showCsRank ? 'Yes' : 'No';

        // 4. PET DETAILS
        document.getElementById('val-pet-id').textContent = pet.id || 'N/A';
        document.getElementById('val-pet-lvl').textContent = pet.level || 'N/A';
        document.getElementById('val-pet-exp').textContent = pet.exp ? formatNumber(pet.exp) : 'N/A';
        document.getElementById('val-pet-selected').textContent = pet.isSelected ? 'Yes' : 'No';
        document.getElementById('val-pet-skill').textContent = pet.selectedSkillId || 'N/A';
        document.getElementById('val-pet-skin').textContent = pet.skinId || 'N/A';

        // 5. GUILD INFO
        document.getElementById('val-guild-name').textContent = clan.clanName || 'N/A';
        document.getElementById('val-guild-id').textContent = clan.clanId || 'N/A';
        document.getElementById('val-guild-lvl').textContent = clan.clanLevel || 'N/A';
        document.getElementById('val-guild-members').textContent = clan.capacity ? `${clan.memberNum || 0}/${clan.capacity}` : 'N/A';

        const leaderInfoEl = document.getElementById('val-leader-info');
        if (captain && captain.nickname) {
            leaderInfoEl.textContent = [
                `Name: ${captain.nickname}`,
                `UID: ${captain.accountId || 'N/A'}`,
                `Level: ${captain.level || 'N/A'}`,
                `Likes: ${formatNumber(captain.liked)}`,
                `Created At: ${formatFullDateTime(captain.createAt)}`,
                `Last Login: ${formatFullDateTime(captain.lastLoginAt)}`
            ].join(' | ');
        } else {
            leaderInfoEl.textContent = 'No Guild Leader Information';
        }

        // Complete Raw JSON Display
        document.getElementById('json-raw-display').textContent = JSON.stringify(data, null, 2);

        placeholder.style.display = 'none';
        results.style.display = 'block';

    } catch (err) {
        placeholder.style.display = 'block';
        results.style.display = 'none';
        errorBanner.style.display = 'block';
        errorBanner.textContent = err.message;
    } finally {
        btnText.style.display = 'inline-block';
        btnSpinner.style.display = 'none';
    }
}
