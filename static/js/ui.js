// static/js/ui.js
// 负责处理 UI 交互、地图操作和 DOM 更新

/**
 * 初始化 UI 交互逻辑
 * @param {Object} map - OpenLayers 地图实例
 * @param {Object} state - 全局状态对象 (共享状态)
 * @param {HTMLElement} statusPanel - 状态栏 DOM 元素
 * @param {Object} vectorSource - 共享的 Vector Source
 */
export function initUIHandlers(map, state, statusPanel, vectorSource) {
    // 1. DOM 元素获取
    const mmsiInput = document.getElementById('mmsiInput');
    const queryBtn = document.getElementById('queryBtn');
    const stopBtn = document.getElementById('stopBtn');
    const clearBtn = document.getElementById('clearBtn');
    const shipListContainer = document.getElementById('shipListContainer');
    const trackPanel = document.getElementById('track-panel');
    const trackStart = document.getElementById('trackStart');
    const trackEnd = document.getElementById('trackEnd');
    const playTrackBtn = document.getElementById('playTrackBtn');
    const trackProgress = document.getElementById('track-progress');
    const trackTimeLabel = document.getElementById('track-time-label');

    // 2. 全局状态管理 (用于回放等)
    const replayStates = {};
    let currentReplayMmsi = null;

    // 3. UI 交互逻辑
    // --- 按钮事件监听 ---
    
    // 查询按钮
    queryBtn.addEventListener('click', () => {
        const rawMmsi = mmsiInput.value.trim();
        if (rawMmsi === '') {
            // 全船模式
            state.isFullShipMode = true;
            socket.emit('query_ship', { mmsi: '' });
            socket.emit('get_all_ships_snapshot');
        } else {
            // 指定船只模式
            state.isFullShipMode = false;
            socket.emit('query_ship', { mmsi: rawMmsi });
        }
    });

    // 停止按钮
    stopBtn.addEventListener('click', () => {
        // 无论什么模式，都发送停止信号
        socket.emit('stop_tracking');

        // 2. 清除前端的全船快照定时器（如果有的话）
        if (state.snapshotTimer) {
            clearInterval(state.snapshotTimer);
            state.snapshotTimer = null;
    }

        // 重置状态
        state.isFullShipMode = false;

        // 清空地图上的船只标记
        Object.values(state.shipMarkers).forEach(marker => {
            vectorSource.removeFeature(marker.feature);
        });
        Object.keys(state.shipMarkers).forEach(key => delete state.shipMarkers[key]);

        // 更新状态面板
        statusPanel.textContent = '⏹️ 已停止追踪';
    });

    // 清空地图按钮
    clearBtn.addEventListener('click', () => {
        clearAllShips(map, state, shipListContainer, vectorSource);
        statusPanel.textContent = '🧹 地图已清空';
    });

    // --- 轨迹回放逻辑 ---
    
    // 全局暴露的轨迹按钮点击事件 (供事件委托调用)
    window.openTrack = function(mmsi) {
        currentReplayMmsi = mmsi;
        const now = new Date();
        const yesterday = new Date(now.getTime() - 24 * 60 * 60 * 1000);
        trackEnd.value = now.toISOString().slice(0, 16);
        trackStart.value = yesterday.toISOString().slice(0, 16);
        trackPanel.style.display = 'flex';
        
        const stateObj = replayStates[mmsi];
        if (stateObj) {
            playTrackBtn.textContent = stateObj.timer ? '⏸ 暂停' : '▶ 继续';
        } else {
            playTrackBtn.textContent = '▶ 回放';
        }
        trackProgress.value = 0;
        trackTimeUpLabel.textContent = '就绪';
    };

    // 播放/暂停按钮
    playTrackBtn.addEventListener('click', () => {
        if (!currentReplayMmsi) return;
        const stateObj = replayStates[currentReplayMmsi];
        
        if (!stateObj || !stateObj.data) {
            const start = trackStart.value;
            const end = trackEnd.value;
            if (!start || !end) {
                statusPanel.textContent = '请先选择时间范围';
                return;
            }
            socket.emit('get_ship_track', { mmsi: currentReplayMmsi, start_time: start, end_time: end });
            statusPanel.textContent = `🚀 正在加载 ${currentReplayMmsi} 的历史轨迹...`;
            return;
        }
        
        toggleReplay(currentReplayMmsi, stateObj, map, playTrackBtn, trackProgress, trackTimeLabel, statusPanel);
    });

    // 进度条拖动
    trackProgress.addEventListener('input', () => {
        if (!currentReplayMmsi) return;
        const stateObj = replayStates[currentReplayMmsi];
        if (!stateObj || !stateObj.data) return;
        
        const index = Math.floor((trackProgress.value / 100) * (stateObj.data.length - 1));
        updateReplayView(stateObj, index, map, trackTimeLabel, statusPanel);
    });

    // --- 辅助函数 ---
    
    /**
     * 切换回放状态 (播放/暂停)
     */
    function toggleReplay(mmsi, stateObj, map, playBtn, progress, timeLabel, statusPanel) {
        if (stateObj.timer) {
            clearInterval(stateObj.timer);
            stateObj.timer = null;
            playBtn.textContent = '▶ 继续';
            statusPanel.textContent = `⏸️ ${mmsi} 的回放已暂停`;
        } else {
            playBtn.textContent = '⏸ 暂停';
            let currentIndex = Math.max(1, Math.floor((progress.value / 100) * (stateObj.data.length - 1)));
            
            stateObj.timer = setInterval(() => {
                if (currentIndex >= stateObj.data.length - 1) {
                    clearInterval(stateObj.timer);
                    stateObj.timer = null;
                    playBtn.textContent = '▶ 回放';
                    statusPanel.textContent = `🏁 ${mmsi} 的回放已结束`;
                    return;
                }
                currentIndex++;
                updateReplayView(stateObj, currentIndex, map, timeLabel, statusPanel);
                progress.value = (currentIndex / (stateObj.data.length - 1)) * 100;
            }, 100);
        }
    }

    /**
     * 更新回放视图 (位置、时间、状态栏)
     */
    function updateReplayView(stateObj, index, map, timeLabel, statusPanel) {
        const point = stateObj.data[index];
        const coord = stateObj.lineCoords[index];
        
        // 1. 更新红点位置
        stateObj.replayFeature.setGeometry(new ol.geom.Point(coord));
        
        // 2. 更新时间与状态栏
        const displayName = point[4] || stateObj.mmsi;
        const destination = point[5] || 'N/A';
        const eta = point[6] || 'N/A';
        const timestamp = point[7];
        
        timeLabel.textContent = timestamp;
        statusPanel.textContent = `🎬 回放中: ${displayName} | 目的港: ${destination} | ETA: ${eta} | ${timestamp}`;
    }

    /**
     * 清空所有船只 (地图与列表)
     */
    function clearAllShips(map, state, container, vectorSource) {
        // 清除地图标记：从 Source 中移除所有 Feature
        Object.values(state.shipMarkers).forEach(marker => {
            if (marker.feature) {
                vectorSource.removeFeature(marker.feature);
            }
        });
        state.shipMarkers = {};

        // 清除列表
        container.innerHTML = '<div class="empty-msg">暂无追踪船只</div>';
        
        // 停止所有回放
        Object.keys(replayStates).forEach(mmsi => {
            if (replayStates[mmsi].timer) clearInterval(replayStates[mmsi].timer);
            if (replayStates[mmsi].replayLayer) map.removeLayer(replayStates[mmsi].replayLayer);
            if (replayStates[mmsi].lineLayer) map.removeLayer(replayStates[mmsi].lineLayer);
        });
        // 修改后
        Object.keys(replayStates).forEach(key => delete replayStates[key]);
        trackPanel.style.display = 'none';
    }

    // 将必要的函数挂载到全局或 state 上，供 socket.js 调用
    state.clearAllShips = clearAllShips;
    window.replayUtils = { replayStates, currentReplayMmsi };
}