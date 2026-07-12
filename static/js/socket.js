// static/js/socket.js
// 负责处理所有的 Socket.IO 通信逻辑

/**
 * 初始化 Socket.IO 监听器
 * @param {Object} map - OpenLayers 地图实例
 * @param {Object} state - 全局状态对象 (用于存储 shipMarkers 等)
 * @param {HTMLElement} shipListContainer - 船只列表的 DOM 容器
 * @param {HTMLElement} statusPanel - 状态栏的 DOM 元素
 * @param {Object} vectorSource - OpenLayers Vector Source 用于管理船只标记
 */
export function initSocketHandlers(map, state, shipListContainer, statusPanel, vectorSource) {
    const socket = io();
    
    // 获取独立的标签页容器
    const trackingContainer = document.getElementById('tracking-container') || shipListContainer;
    const historyContainer = document.getElementById('history-container');

    // ✅ 新增：连接成功后，立即请求一次全船快照
    socket.on('connect', () => {
        console.log('Socket 已连接，正在请求初始快照...');
        socket.emit('all_ships_snapshot');
    });

    // --- 辅助函数：渲染船只列表项 (优化版) ---
    function renderShipItem(shipData, container) {
        const { mmsi, ship_name, speed, course, destination, eta } = shipData;
        // 处理显示名称，防止空值
        const displayName = (ship_name && ship_name.trim() !== '') ? ship_name.trim() : String(mmsi);

        // 尝试查找现有的 DOM 元素
        let item = document.getElementById(`ship-item-${mmsi}`);
        if (!item) {
            // --- 首次创建 ---
            item = document.createElement('div');
            item.id = `ship-item-${mmsi}`;
            item.className = 'ship-item';
            // 使用模板字符串构建初始结构
            item.innerHTML = `
                <div class="ship-info">
                    <div class="ship-icon"></div>
                    <div class="ship-details">
                        <b class="ship-name">${displayName}</b>
                        <div class="ship-stats" style="font-size:12px;color:#666;margin-top:4px;">
                            速度: ${speed || 'N/A'} 节 | 航向: ${course || 'N/A'}° | 目的港： ${destination || 'N/A'} | ETA: ${eta || 'N/A'}
                        </div>
                    </div>
                </div>
                <button class="btn-track" data-mmsi="${mmsi}">📼 轨迹</button>
            `;
            container.appendChild(item);
        }

        // --- 更新数据 (无论新老都执行，保证数据同步) ---
        // 1. 安全更新船名
        const nameEl = item.querySelector('.ship-name');
        if (nameEl) nameEl.textContent = displayName;

        // 2. 拼接并更新统计信息
        const statsEl = item.querySelector('.ship-stats');
        if (statsEl) {
            const statsText = [
                `速度: ${speed != null ? speed + ' 节' : 'N/A'}`,
                `航向: ${course != null ? course + '°' : 'N/A'}`,
                `目的港: ${destination || 'N/A'}`,
                `ETA: ${eta || 'N/A'}`
            ].join(' | ');
            statsEl.textContent = statsText;
        }
        return item;
    }

    // 1. 单船/多船实时位置更新 (ship_location)
    socket.on('ship_location', function(msg) {
        const { mmsi, lat, lon, speed, course, ship_name, destination, eta } = msg;
        
        // ✅ 修复1：显式加括号，并过滤 Null Island (0,0)
        if (!mmsi || lat == null || lon == null) return;
        if ((lat === 90 && lon === 180) || (lat === 0 && lon === 0)) return;

        const displayName = (ship_name && ship_name.trim() !== '') ? ship_name.trim() : mmsi;
        const coordinates = ol.proj.fromLonLat([lon, lat]);

        // 更新状态栏
        statusPanel.textContent = `最新数据: ${displayName} | 速度: ${speed || 'N/A'}节 | 航向: ${course || 'N/A'}° | 目的地: ${destination || 'N/A'} | ETA: ${eta || 'N/A'}`;

        // --- 核心修复：复用 Feature 和 Source ---
        let marker = state.shipMarkers[mmsi];
        if (marker) {
            // 更新现有 Feature 的位置
            marker.feature.setGeometry(new ol.geom.Point(coordinates));
            // ✅ 修复2：只在字段有值时才更新，防止 undefined 覆盖有效数据
            if (ship_name !== undefined && ship_name !== null) marker.ship_name = ship_name;
            if (destination !== undefined && destination !== null) marker.destination = destination;
            if (eta !== undefined && eta !== null) marker.eta = eta;
            if (speed !== undefined && speed !== null) marker.speed = speed;
            if (course !== undefined && course !== null) marker.course = course;
        } else {
            // 创建新的 Feature
            const feature = new ol.Feature({
                geometry: new ol.geom.Point(coordinates)
            });
            feature.setStyle(new ol.style.Style({
                image: new ol.style.Circle({
                    radius: 6,
                    fill: new ol.style.Fill({ color: '#00ff00' }),
                    stroke: new ol.style.Stroke({ color: '#fff', width: 2 })
                })
            }));
            // 添加到共享的 Source 中
            vectorSource.addFeature(feature);
            // 记录引用
            state.shipMarkers[mmsi] = { 
                feature, 
                ship_name: ship_name || '', 
                destination: destination || '', 
                eta: eta || '', 
                speed: speed || '', 
                course: course || '' 
            };
        }

        // 自动调整视图
        const markerCount = Object.keys(state.shipMarkers).length;
        if (markerCount > 1) {
            const extent = ol.extent.createEmpty();
            Object.values(state.shipMarkers).forEach(m => ol.extent.extend(extent, m.feature.getGeometry().getExtent()));
            map.getView().fit(extent, { padding: [50, 50, 50, 50], duration: 1000 });
        } else {
            map.getView().animate({ center: coordinates, zoom: 12, duration: 1000 });
        }

        // 更新右侧列表（传入完整的 marker 数据，确保字段不为 undefined）
        const currentMarker = state.shipMarkers[mmsi];
        renderShipItem({
            mmsi,
            lat,
            lon,
            speed: currentMarker.speed,
            course: currentMarker.course,
            ship_name: currentMarker.ship_name,
            destination: currentMarker.destination,
            eta: currentMarker.eta
        }, trackingContainer);
    });

    // 2. 状态更新 (status_update)
    socket.on('status_update', function(data) {
        const msg = data.msg || data;
        statusPanel.textContent = msg;
        if (msg === '停止追踪') {
            // 可以触发 UI 重置
        }
    });

    // 3. 历史数据更新 (history_data)
    socket.on('history_data', function(data) {
        const historyList = data.history;
        // 确保容器存在且数据有效
        if (historyContainer && historyList && historyList.length > 0) {
            // 清空旧的历史记录
            historyContainer.innerHTML = '';
            const histDiv = document.createElement('div');
            historyList.forEach(item => {
                // ✅ 修改点 1：使用键名获取数据，而不是下标
                const mmsiStr = item.mmsi_list || '未知MMSI';
                let timeStr = item.created_at || '';
                // ✅ 修改点 2：美化时间显示 (去掉 T，截取秒)
                if (timeStr) {
                    timeStr = timeStr.replace('T', ' ').substring(0, 19);
                } else {
                    timeStr = '时间未知';
                }
                const div = document.createElement('div');
                div.className = 'ship-item';
                // 渲染 HTML
                div.innerHTML = `
                    <div class="ship-info">
                        <div class="ship-icon"></div>
                        <div>
                            <b>${mmsiStr}</b><br>
                            <span style="font-size:12px;color:#666;">${timeStr}</span>
                        </div>
                    </div>`;
                // 点击事件
                div.onclick = () => {
                    const input = document.getElementById('mmsiInput');
                    const btn = document.getElementById('queryBtn');
                    if (input && btn) {
                         // 如果 mmsiStr 存在，去除首尾空格后直接赋值-保留逗号分隔的多个 MMSI
                        input.value = mmsiStr ? mmsiStr.trim() : '';
                        btn.click();
                        // 自动切换到实时追踪标签页
                        if (typeof switchTab === 'function') {
                            switchTab('tracking');
                        }
                    }
                };
                histDiv.appendChild(div);
            });
            historyContainer.appendChild(histDiv);
        } else if (historyContainer) {
            // 可选：如果没有数据时的提示
            historyContainer.innerHTML = '<div style="text-align:center;color:#999;padding:20px;">暂无历史记录</div>';
        }
    });

    // 4. 批量位置更新（配合后端节流）
    socket.on('batch_ship_location', function(data) {
        const ships = data.ships || [];
        ships.forEach(msg => {
            const { mmsi, lat, lon, speed, course, ship_name, destination, eta } = msg;
            if (!mmsi || lat == null || lon == null) return;
            
            const coordinates = ol.proj.fromLonLat([lon, lat]);
            let marker = state.shipMarkers[mmsi];

            // --- 1. 更新地图标记 ---
            if (marker) {
                marker.feature.setGeometry(new ol.geom.Point(coordinates));
                // ✅ 修复：防止 undefined 覆盖
                if (ship_name !== undefined && ship_name !== null) marker.ship_name = ship_name;
                if (destination !== undefined && destination !== null) marker.destination = destination;
                if (eta !== undefined && eta !== null) marker.eta = eta;
                if (speed !== undefined && speed !== null) marker.speed = speed;
                if (course !== undefined && course !== null) marker.course = course;
            } else {
                const feature = new ol.Feature({
                    geometry: new ol.geom.Point(coordinates)
                });
                feature.setStyle(new ol.style.Style({
                    image: new ol.style.Circle({
                        radius: 6,
                        fill: new ol.style.Fill({ color: '#00ff00' }),
                        stroke: new ol.style.Stroke({ color: '#fff', width: 2 })
                    })
                }));
                vectorSource.addFeature(feature);
                state.shipMarkers[mmsi] = { 
                    feature, 
                    ship_name: ship_name || '', 
                    destination: destination || '', 
                    eta: eta || '', 
                    speed: speed || '', 
                    course: course || '' 
                };
            }

            // --- 2. 更新右侧列表 ---
            // 使用 state 中的数据确保一致性
            const currentMarker = state.shipMarkers[mmsi];
            renderShipItem({
                mmsi,
                speed: currentMarker.speed,
                course: currentMarker.course,
                ship_name: currentMarker.ship_name,
                destination: currentMarker.destination,
                eta: currentMarker.eta
            }, trackingContainer);
        });

        // 批量更新后，统一调整一次视图
        if (Object.keys(state.shipMarkers).length > 0) {
            const extent = ol.extent.createEmpty();
            Object.values(state.shipMarkers).forEach(marker => ol.extent.extend(extent, marker.feature.getGeometry().getExtent()));
            map.getView().fit(extent, { padding: [50, 50, 50, 50], duration: 1000 });
        }
    });

    // 5. 全船快照数据处理 (all_ships_snapshot)
    socket.on('all_ships_snapshot', function(data) {
        const ships = data.ships || [];
        
        // ✅ 修改：全船快照时，清空右侧列表
        trackingContainer.innerHTML = '';
        
        statusPanel.textContent = `📸 全船快照更新于 ${new Date().toLocaleTimeString()} (共 ${ships.length} 艘)`;
        
        const currentMmsis = new Set(Object.keys(state.shipMarkers));
        const newMmsis = new Set();

        ships.forEach(ship => {
            const { mmsi, lat, lon, ship_name, speed, course, destination, eta } = ship;
            if (!mmsi || lat == null || lon == null) return;
            
            newMmsis.add(mmsi);
            const coordinates = ol.proj.fromLonLat([lon, lat]);

            // --- 1. 更新地图标记 ---
            let marker = state.shipMarkers[mmsi];
            if (marker) {
                marker.feature.setGeometry(new ol.geom.Point(coordinates));
                // ✅ 修复：防止 undefined 覆盖
                if (ship_name !== undefined && ship_name !== null) marker.ship_name = ship_name;
                if (destination !== undefined && destination !== null) marker.destination = destination;
                if (eta !== undefined && eta !== null) marker.eta = eta;
                if (speed !== undefined && speed !== null) marker.speed = speed;
                if (course !== undefined && course !== null) marker.course = course;
            } else {
                const feature = new ol.Feature({
                    geometry: new ol.geom.Point(coordinates)
                });
                feature.setStyle(new ol.style.Style({
                    image: new ol.style.Circle({
                        radius: 6,
                        fill: new ol.style.Fill({ color: '#00ff00' }),
                        stroke: new ol.style.Stroke({ color: '#fff', width: 2 })
                    })
                }));
                vectorSource.addFeature(feature);
                state.shipMarkers[mmsi] = { 
                    feature, 
                    ship_name: ship_name || '', 
                    destination: destination || '', 
                    eta: eta || '', 
                    speed: speed || '', 
                    course: course || '' 
                };
            }
        });

        // --- 3. 清理已消失的船只 ---
        currentMmsis.forEach(mmsi => {
            if (!newMmsis.has(mmsi)) {
                const marker = state.shipMarkers[mmsi];
                if (marker && marker.feature) {
                    vectorSource.removeFeature(marker.feature);
                }
                delete state.shipMarkers[mmsi];
                // 同时从列表中移除 DOM 元素
                const listEl = trackingContainer.querySelector(`#ship-item-${mmsi}`);
                if (listEl) listEl.remove();
            }
        });

        if (ships.length === 0) {
            statusPanel.textContent = '📸 全船快照：当前区域内暂无船只';
        }
    });

    // --- 事件委托：处理轨迹按钮点击 ---
    trackingContainer.addEventListener('click', function(e) {
        const btn = e.target.closest('.btn-track');
        if (btn) {
            const mmsi = btn.getAttribute('data-mmsi');
            if (window.openTrack) {
                window.openTrack(mmsi);
            }
        }
    });

    // --- 标签页切换逻辑 ---
    function switchTab(tabName) {
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.classList.toggle('active', btn.getAttribute('data-tab') === tabName);
        });
        document.querySelectorAll('.tab-content').forEach(content => {
            content.classList.toggle('active', content.id === `${tabName}-container`);
        });
        // 新增：切换到历史记录标签时，重新拉取
        if (tabName === 'history') {
            socket.emit('load_history');
        }
    }
    // 绑定标签页点击事件
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            switchTab(btn.getAttribute('data-tab'));
        });
    });

    return socket;
}