// ==UserScript==
// @name         Heatmap preview
// @namespace    http://tampermonkey.net/
// @version      2024-11-20
// @description  Parses coordate output to create a heatmap
// @author       Glen Watson
// @match        https://awbw.amarriner.com/prevmaps.php?maps_id=*
// @icon         https://www.google.com/s2/favicons?sz=64&domain=amarriner.com
// @grant        none
// ==/UserScript==

(function() {
  'use strict';
  function parseDataIntoDataPoints(data) {
    const dataPoints = [];
    for (const dataPoint of data.split(';')) {
      const match = dataPoint.match(/\((\d+), (\d+)\) (\d+)/);
      if (match) {
        dataPoints.push({x: match[1], y: match[2], count: match[3]});
      }
    }
    return dataPoints;
  }

  function getColor(percent) {
    // percent from 0 to 1
    const hue = ((1-percent)*120).toString(10);
    return "hsla(" + hue + ",100%,50%,0.5)";
  }
  function addHeatMapSquare(x, y, color) {
    const span = document.createElement('span');
    span.style.left = (x * 16) + "px";
    span.style.top = (y * 16) + "px";
    span.style.width = "16px";
    span.style.height = "16px";
    span.style.position = "absolute";
    span.style.border = "0px";
    span.style.zIndex = "100";
    span.style.backgroundColor = color;
    document.querySelector('#gamemap').appendChild(span);
  }

  function heatmapData(data) {
    const dataPoints = parseDataIntoDataPoints(data);
    const maxDataPointCount = Math.max(...dataPoints.map(dp => parseInt(dp.count)));
    for (const dataPoint of dataPoints) {
      const frequencyPercent = dataPoint.count / maxDataPointCount;
      addHeatMapSquare(dataPoint.x, dataPoint.y, getColor(frequencyPercent));
    }
  }

  function buildForm() {
    const heatmapCoordsLabelEle = document.createTextNode('Enter coordinates from output:');
    const heatmapCoordsInputEle = document.createElement('input');
    heatmapCoordsInputEle.id = 'heatmap-coords-input';
    heatmapCoordsInputEle.placeholder = "Coordinates e.g. (1, 2) 3;";
    const heatmapCoordsButtonEle = document.createElement('button');
    heatmapCoordsButtonEle.innerText = 'Generate Heatmap';
    heatmapCoordsButtonEle.onclick = (e) => {
      heatmapData(heatmapCoordsInputEle.value);
      heatmapCoordsButtonEle.disabled = true;
    };

    // Create a div to hold the form
    const heatmapEle = document.createElement('div');
    heatmapEle.id = 'heatmap-coords';
    heatmapEle.appendChild(heatmapCoordsLabelEle);
    heatmapEle.appendChild(heatmapCoordsInputEle);
    heatmapEle.appendChild(heatmapCoordsButtonEle);

    // Attach the form to the page
    const container = document.querySelector('#map-categories');
    container.insertBefore(heatmapEle, container.firstChild);
  }
  buildForm();

})();