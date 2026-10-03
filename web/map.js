let map, layer;
const markers = new Map();
export function init_map() {
  if (!window.L) throw new Error('Map library unavailable. Check your connection and refresh.');
  map = L.map('map', { zoomControl: true }).setView([22.308, 113.9185], 8);
  L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors', maxZoom: 19
  }).addTo(map);
  L.circle([22.308,113.9185], { radius:3500, color:'#007aff', weight:1, fillOpacity:0.06 }).addTo(map);
  layer=L.layerGroup().addTo(map);
}
export function update_map(json, selected) {
  if (!map) return;
  const planes=JSON.parse(json), ids=new Set(planes.map(p=>p.id));
  for (const [id,marker] of markers) if (!ids.has(id)) {layer.removeLayer(marker);markers.delete(id);}
  for (const p of planes) {
    const icon=L.divIcon({className:'plane-marker',iconSize:[26,26],iconAnchor:[13,13],
      html:`<svg viewBox="0 0 32 32" role="img" aria-label="Aircraft" style="transform:rotate(${p.track}deg);color:${p.cathay?'#e99219':'#007aff'}" class="${p.id===selected?'selected':''}"><path d="M16 2l3 11 11 6v3l-11-3v6l4 3v2l-7-2-7 2v-2l4-3v-6L2 22v-3l11-6z"/></svg>`});
    let marker=markers.get(p.id);
    if (!marker) {
      marker=L.marker([p.lat,p.lon],{icon,keyboard:true}).addTo(layer);
      marker.on('click',()=>document.dispatchEvent(new CustomEvent('aircraft-select',{detail:p.id})));
      markers.set(p.id,marker);
    } else {marker.setLatLng([p.lat,p.lon]);marker.setIcon(icon);}
    const tip=document.createElement('div');tip.textContent=`${p.callsign} · ${p.type_code||'Type unavailable'} · ${p.registration||'Registration unavailable'} · ${p.ground?'GROUND':Math.round(p.altitude)+' FT'} · ${Math.round(p.speed)} KT`;
    marker.unbindTooltip().bindTooltip(tip);marker.options.title=p.callsign;
    const el=marker.getElement();if(el){el.setAttribute('aria-label',p.callsign);el.setAttribute('data-aircraft-id',p.id);}
  }
}
