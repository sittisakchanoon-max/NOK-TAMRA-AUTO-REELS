// NOK TAMRA AUTO REELS - Core Frontend Logic

let currentTab = 'dashboard';
let statsTimer = null;
let activeVideoForDetail = null;

document.addEventListener('DOMContentLoaded', () => {
    initNavigation();
    loadDashboardStats();
    loadSettings();
    startPolling();
});

// Navigation Handling
function initNavigation() {
    const navItems = document.querySelectorAll('.nav-item');
    navItems.forEach(item => {
        item.addEventListener('click', () => {
            const tabName = item.getAttribute('data-tab');
            switchTab(tabName);
        });
    });
}

function switchTab(tabName) {
    currentTab = tabName;
    document.querySelectorAll('.nav-item').forEach(el => {
        el.classList.toggle('active', el.getAttribute('data-tab') === tabName);
    });
    document.querySelectorAll('.tab-pane').forEach(pane => {
        pane.classList.remove('active');
    });

    const target = document.getElementById(`tab-${tabName}`);
    if (target) {
        target.classList.add('active');
    }

    if (tabName === 'dashboard') loadDashboardStats();
    if (tabName === 'videos') loadVideos();
    if (tabName === 'settings') loadSettings();
    if (tabName === 'logs') loadLogs();
}

function startPolling() {
    setInterval(() => {
        if (currentTab === 'dashboard') loadDashboardStats();
        if (currentTab === 'logs') loadLogs();
    }, 10000);
}

// 1. Dashboard Logic
async function loadDashboardStats() {
    try {
        const res = await fetch('/api/dashboard/stats');
        const data = await res.json();

        // Metrics
        document.getElementById('metric-total').textContent = data.metrics.total_videos;
        document.getElementById('metric-pending').textContent = data.metrics.pending_videos;
        document.getElementById('metric-analyzed').textContent = data.metrics.analyzed_videos;
        document.getElementById('metric-published').textContent = data.metrics.published_videos;
        document.getElementById('metric-failed').textContent = data.metrics.failed_videos;

        // Service badges
        const driveBadge = document.getElementById('status-drive');
        if (data.google_drive.status === 'CONNECTED') {
            driveBadge.className = 'status-pill';
            driveBadge.innerHTML = '<span class="status-dot"></span> เชื่อมต่อแล้ว';
        } else {
            driveBadge.className = 'status-pill';
            driveBadge.style.color = '#ef4444';
            driveBadge.style.background = 'rgba(239, 68, 68, 0.15)';
            driveBadge.innerHTML = 'ยังไม่ระบุโฟลเดอร์';
        }

        const fbBadge = document.getElementById('status-facebook');
        if (data.facebook_page.status === 'CONNECTED') {
            fbBadge.className = 'status-pill';
            fbBadge.innerHTML = '<span class="status-dot"></span> เชื่อมต่อแล้ว';
        } else {
            fbBadge.className = 'status-pill';
            fbBadge.style.color = '#f59e0b';
            fbBadge.style.background = 'rgba(245, 158, 11, 0.15)';
            fbBadge.innerHTML = 'รอตั้งค่า Token';
        }

        // Times
        const lastRunText = data.scheduler.last_run ? new Date(data.scheduler.last_run).toLocaleTimeString('th-TH') : 'ยังไม่มี';
        document.getElementById('stat-last-run').textContent = lastRunText;

        const nextRunText = data.scheduler.next_run ? new Date(data.scheduler.next_run).toLocaleTimeString('th-TH') : 'รอรอบถัดไป';
        document.getElementById('stat-next-run').textContent = nextRunText;

        const scanBtn = document.getElementById('btn-scan-now');
        if (data.scheduler.is_processing) {
            scanBtn.disabled = true;
            scanBtn.textContent = '⏳ กำลังประมวลผลคลิป...';
        } else {
            scanBtn.disabled = false;
            scanBtn.innerHTML = '🚀 ตรวจสอบคลิป Google Drive ทันที';
        }

    } catch (e) {
        console.error('Error fetching stats:', e);
    }
}

async function triggerManualScan() {
    const scanBtn = document.getElementById('btn-scan-now');
    scanBtn.disabled = true;
    scanBtn.textContent = '⏳ กำลังตรวจสอบและวิเคราะห์...';

    try {
        const res = await fetch('/api/dashboard/trigger', { method: 'POST' });
        const data = await res.json();
        alert('✅ เริ่มกระบวนการสแกนแล้ว!');
        loadDashboardStats();
    } catch (e) {
        alert('❌ เกิดข้อผิดพลาด: ' + e.message);
    } finally {
        setTimeout(loadDashboardStats, 3000);
    }
}

// 2. Videos Logic
async function loadVideos() {
    const container = document.getElementById('videos-container');
    container.innerHTML = '<div style="text-align:center; padding: 40px; color: var(--text-dim);">กำลังโหลดคลิป...</div>';

    try {
        const res = await fetch('/api/videos');
        const videos = await res.json();

        if (videos.length === 0) {
            container.innerHTML = `
                <div style="text-align:center; padding: 50px 20px; color: var(--text-muted);">
                    <div style="font-size: 38px; margin-bottom: 10px;">📂</div>
                    <div style="font-weight: 700; font-size: 16px;">ยังไม่มีคลิปในระบบ</div>
                    <p style="font-size: 13px; color: var(--text-dim); margin-top: 6px;">ระบบจะตรวจสอบไฟล์ใน Google Drive อัตโนมัติทุก 15 นาที หรือกดปุ่ม 'ตรวจสอบทันที' ในแท็บแรก</p>
                </div>
            `;
            return;
        }

        container.innerHTML = '';
        videos.forEach(v => {
            const card = document.createElement('div');
            card.className = 'video-card';

            const statusClass = `badge-${(v.status || 'pending').toLowerCase()}`;
            const statusLabel = {
                'PUBLISHED': 'โพสต์แล้ว 🚀',
                'READY_TO_POST': 'วิเคราะห์แล้ว พร้อมโพสต์',
                'ANALYZING': 'AI กำลังวิเคราะห์...',
                'DOWNLOADING': 'กำลังดาวน์โหลด...',
                'FAILED': 'ล้มเหลว',
                'SKIPPED': 'ข้าม (คลิปซ้ำ)',
                'PENDING': 'รอดำเนินการ'
            }[v.status] || v.status;

            const durationStr = v.duration_seconds ? `${Math.round(v.duration_seconds)}s` : '';
            const thumbUrl = v.thumbnail_url || 'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="100" height="60" fill="%231e2433"><rect width="100" height="60"/></svg>';

            card.innerHTML = `
                <div class="video-thumb-wrap">
                    <img class="video-thumb" src="${thumbUrl}" alt="Thumbnail" onerror="this.src=''"/>
                    <span class="video-status-badge ${statusClass}">${statusLabel}</span>
                    ${durationStr ? `<span class="video-duration">${durationStr}</span>` : ''}
                </div>
                <div class="video-body">
                    <div class="video-title">${v.caption_title || v.file_name}</div>
                    <div style="font-size: 11px; color: var(--text-dim); margin-bottom: 8px;">
                        ไฟล์: ${v.file_name} • ${new Date(v.created_at).toLocaleString('th-TH')}
                    </div>
                    ${v.caption_body ? `<div class="video-caption">${escapeHtml(v.caption_body)}</div>` : ''}
                    ${v.hashtags ? `<div class="video-hashtags">${escapeHtml(v.hashtags)}</div>` : ''}
                    
                    ${v.facebook_reel_url ? `
                        <a href="${v.facebook_reel_url}" target="_blank" class="btn btn-secondary btn-sm" style="margin-bottom: 10px; display: inline-flex;">
                            🔗 ดูคลิปบน Facebook Reels
                        </a>
                    ` : ''}

                    <div class="video-actions">
                        <button class="btn btn-secondary btn-sm" onclick="openDetailModal('${v.id}')">
                            🔍 ผลวิเคราะห์ AI
                        </button>
                        ${v.status !== 'PUBLISHED' ? `
                            <button class="btn btn-primary btn-sm" onclick="publishSingleVideo('${v.id}')">
                                📤 โพสต์ Reel ทันที
                            </button>
                        ` : ''}
                    </div>
                </div>
            `;
            container.appendChild(card);
        });

    } catch (e) {
        container.innerHTML = `<div style="color:var(--status-error); padding:20px;">โหลดข้อมูลไม่สำเร็จ: ${e.message}</div>`;
    }
}

async function publishSingleVideo(id) {
    if (!confirm('ยืนยันการโพสต์คลิปนี้ไปยัง Facebook Reels ทันที?')) return;
    try {
        const res = await fetch(`/api/videos/${id}/publish`, { method: 'POST' });
        const data = await res.json();
        if (data.success) {
            alert('🎉 โพสต์ Facebook Reels สำเร็จแล้ว!\nลิงก์: ' + data.reel_url);
            loadVideos();
        } else {
            alert('❌ โพสต์ไม่สำเร็จ: ' + (data.error || 'กรุณาตรวจสอบ Token ในหน้า Settings'));
        }
    } catch (e) {
        alert('❌ เกิดข้อผิดพลาด: ' + e.message);
    }
}

async function openDetailModal(id) {
    try {
        const res = await fetch(`/api/videos/${id}`);
        const v = await res.json();
        activeVideoForDetail = v;

        document.getElementById('modal-title').textContent = v.caption_title || v.file_name;
        
        const ai = v.ai_analysis || {};
        const detailHtml = `
            <div style="font-size: 13px; line-height: 1.6;">
                <div style="margin-bottom: 10px;">
                    <strong style="color: var(--primary-yellow);">📖 สรุปเนื้อหา:</strong>
                    <div style="color: var(--text-muted);">${escapeHtml(ai.content_summary || 'ไม่มีข้อมูล')}</div>
                </div>
                <div style="margin-bottom: 10px;">
                    <strong style="color: var(--primary-yellow);">🎬 ลำดับภาพและฉาก:</strong>
                    <div style="color: var(--text-muted);">${escapeHtml(ai.scenes_breakdown || 'ไม่มีข้อมูล')}</div>
                </div>
                <div style="margin-bottom: 10px;">
                    <strong style="color: var(--primary-yellow);">🎙️ เสียงและบทบรรยาย:</strong>
                    <div style="color: var(--text-muted);">${escapeHtml(ai.speech_and_audio || 'ไม่มีข้อมูล')}</div>
                </div>
                <div style="margin-bottom: 10px;">
                    <strong style="color: var(--primary-yellow);">⭐ จุดเด่นของคลิป:</strong>
                    <div style="color: var(--text-muted);">${escapeHtml(ai.highlights || 'ไม่มีข้อมูล')}</div>
                </div>
                <div style="margin-bottom: 10px;">
                    <strong style="color: var(--primary-yellow);">🎭 อารมณ์และกลุ่มเป้าหมาย:</strong>
                    <div style="color: var(--text-muted);">${escapeHtml(ai.vibe_and_mood || '')} • ${escapeHtml(ai.target_audience || '')}</div>
                </div>
            </div>
            
            <div style="margin-top: 14px;">
                <label class="form-label">แก้ไขแคปชั่น:</label>
                <textarea id="modal-caption-edit" class="form-input" style="height: 90px;">${escapeHtml(v.caption_body || '')}</textarea>
            </div>
            <div style="margin-top: 10px;">
                <label class="form-label">แก้ไข Hashtags:</label>
                <input id="modal-hashtags-edit" class="form-input" value="${escapeHtml(v.hashtags || '')}"/>
            </div>
            <div style="margin-top: 16px; display: flex; gap: 8px;">
                <button class="btn btn-primary" onclick="saveEditedCaption('${v.id}')">💾 บันทึกการแก้ไข</button>
                <button class="btn btn-secondary" onclick="closeModal()">ปิด</button>
            </div>
        `;
        document.getElementById('modal-content').innerHTML = detailHtml;
        document.getElementById('detail-modal').classList.add('active');
    } catch (e) {
        alert('โหลดรายละเอียดไม่สำเร็จ: ' + e.message);
    }
}

function closeModal() {
    document.getElementById('detail-modal').classList.remove('active');
}

async function saveEditedCaption(id) {
    const caption = document.getElementById('modal-caption-edit').value;
    const hashtags = document.getElementById('modal-hashtags-edit').value;

    try {
        const res = await fetch(`/api/videos/${id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ caption_body: caption, hashtags: hashtags })
        });
        const data = await res.json();
        alert('✅ บันทึกแคปชั่นแล้ว');
        closeModal();
        loadVideos();
    } catch (e) {
        alert('❌ บันทึกไม่สำเร็จ: ' + e.message);
    }
}

// 3. Settings Logic
async function loadSettings() {
    try {
        const res = await fetch('/api/settings');
        const s = await res.json();

        document.getElementById('set-gdrive-folder').value = s.gdrive_folder_id || '';
        document.getElementById('set-interval').value = s.gdrive_check_interval_minutes || 15;
        document.getElementById('set-fb-page').value = s.facebook_page_id || '';
        document.getElementById('set-auto-publish').checked = !!s.auto_publish;

        if (s.facebook_page_access_token_set) {
            document.getElementById('set-fb-token').placeholder = `ตั้งค่าแล้ว (${s.facebook_page_access_token_masked})`;
        }
        if (s.gemini_api_key_set) {
            document.getElementById('set-gemini-key').placeholder = `ตั้งค่าแล้ว (${s.gemini_api_key_masked})`;
        }

        loadStorageStats();
    } catch (e) {
        console.error('Error loading settings:', e);
    }
}

async function saveSettings(e) {
    if (e) e.preventDefault();
    const folderId = document.getElementById('set-gdrive-folder').value;
    const interval = parseInt(document.getElementById('set-interval').value) || 15;
    const pageId = document.getElementById('set-fb-page').value;
    const fbToken = document.getElementById('set-fb-token').value;
    const geminiKey = document.getElementById('set-gemini-key').value;
    const autoPublish = document.getElementById('set-auto-publish').checked;

    const payload = {
        gdrive_folder_id: folderId,
        gdrive_check_interval_minutes: interval,
        facebook_page_id: pageId,
        auto_publish: autoPublish
    };

    if (fbToken && fbToken.trim()) payload.facebook_page_access_token = fbToken.trim();
    if (geminiKey && geminiKey.trim()) payload.gemini_api_key = geminiKey.trim();

    try {
        const res = await fetch('/api/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const data = await res.json();
        alert('✅ บันทึกการตั้งค่าเรียบร้อยแล้ว');
        loadSettings();
    } catch (e) {
        alert('❌ บันทึกไม่สำเร็จ: ' + e.message);
    }
}

async function testFacebookConnection() {
    const btn = document.getElementById('btn-test-fb');
    btn.disabled = true;
    btn.textContent = 'กำลังทดสอบ...';
    try {
        const res = await fetch('/api/settings/test-facebook', { method: 'POST' });
        const data = await res.json();
        if (data.valid) {
            alert(`🎉 เชื่อมต่อสำเร็จ!\nเพจ: ${data.page_name} (ID: ${data.page_id})\nสิทธิ์พร้อมเผยแพร่ Reels`);
        } else {
            alert(`⚠️ ตรวจสอบไม่ผ่าน: ${data.error}`);
        }
    } catch (e) {
        alert('❌ เกิดข้อผิดพลาด: ' + e.message);
    } finally {
        btn.disabled = false;
        btn.textContent = '🧪 ทดสอบเชื่อมต่อ Facebook';
    }
}

async function testDriveConnection() {
    const btn = document.getElementById('btn-test-drive');
    btn.disabled = true;
    btn.textContent = 'กำลังทดสอบ...';
    try {
        const res = await fetch('/api/settings/test-drive', { method: 'POST' });
        const data = await res.json();
        if (data.connected) {
            alert(`✅ เชื่อมต่อ Google Drive สำเร็จ!\nพบไฟล์วิดีโอ: ${data.video_count} คลิป\nตัวอย่าง: ${data.sample_files.join(', ')}`);
        } else {
            alert(`⚠️ ไม่พบวิดีโอในโฟลเดอร์ หรือระบุ Folder ID ไม่ถูกต้อง`);
        }
    } catch (e) {
        alert('❌ เกิดข้อผิดพลาด: ' + e.message);
    } finally {
        btn.disabled = false;
        btn.textContent = '📁 ทดสอบโฟลเดอร์ Google Drive';
    }
}

async function loadStorageStats() {
    try {
        const res = await fetch('/api/settings/storage');
        const st = await res.json();
        document.getElementById('storage-used-mb').textContent = `${st.used_total_mb} MB / ${st.max_allowed_mb} MB`;
        document.getElementById('storage-bar').style.width = `${st.percentage_used}%`;
        document.getElementById('storage-disk-free').textContent = `พื้นที่ว่างบนเซิร์ฟเวอร์: ${st.disk_free_mb} MB`;
    } catch (e) {}
}

async function triggerStorageCleanup() {
    if (!confirm('ต้องการล้างไฟล์วิดีโอชั่วคราวที่ดาวน์โหลดมาแล้วเพื่อประหยัดพื้นที่หรือไม่? (ประวัติและผลวิเคราะห์จะไม่หาย)')) return;
    try {
        const res = await fetch('/api/settings/cleanup-storage', { method: 'POST' });
        const data = await res.json();
        alert(`🧹 ล้างพื้นที่สำเร็จ ลบไป ${data.removed_files} ไฟล์`);
        loadStorageStats();
    } catch (e) {
        alert('❌ ไม่สำเร็จ: ' + e.message);
    }
}

// 4. Logs Logic
async function loadLogs() {
    const container = document.getElementById('logs-container');
    const filter = document.getElementById('log-filter-category').value;

    try {
        const res = await fetch(`/api/logs?category=${filter}`);
        const logs = await res.json();

        if (logs.length === 0) {
            container.innerHTML = '<div style="color:var(--text-dim); text-align:center; padding:30px;">ไม่มีบันทึกข้อมูล</div>';
            return;
        }

        container.innerHTML = logs.map(l => `
            <div class="log-item ${l.level}">
                <div class="log-header">
                    <span class="log-category">[${l.category}] ${l.level}</span>
                    <span>${new Date(l.created_at).toLocaleTimeString('th-TH')}</span>
                </div>
                <div style="color:var(--text-white); font-weight:500;">${escapeHtml(l.message)}</div>
                ${l.details ? `<div style="font-size:10px; color:var(--text-dim); margin-top:2px;">${escapeHtml(l.details)}</div>` : ''}
            </div>
        `).join('');

    } catch (e) {
        container.innerHTML = `<div style="color:var(--status-error);">โหลด Logs ไม่สำเร็จ: ${e.message}</div>`;
    }
}

async function clearLogs() {
    if (!confirm('ล้างประวัติการทำงานทั้งหมดหรือไม่?')) return;
    try {
        await fetch('/api/logs', { method: 'DELETE' });
        loadLogs();
    } catch (e) {}
}

function escapeHtml(str) {
    if (!str) return '';
    return str.replace(/&/g, "&amp;")
              .replace(/</g, "&lt;")
              .replace(/>/g, "&gt;")
              .replace(/"/g, "&quot;")
              .replace(/'/g, "&#039;");
}
