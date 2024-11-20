data = "...";

function parseDataIntoDataPoints(data) {
  dataPoints = [];
  for (const dataPoint of data.split(';')) {
    dataPoints.push(parseDataPoint(dataPoint));
  }
  return dataPoints;
}
function parseDataPoint(dataPoint) {
  const match = dataPoint.match(/\((\d+), (\d+)\) (\d+)/);
  return {x: match[1], y: match[2], count: match[3]};
}

function getColor(percent) {
  // percent from 0 to 1
  const hue = ((1-percent)*120).toString(10);
  return "hsla(" + hue + ",100%,50%,0.5)";
}
function addHeatMapSquare(x, y, color) {
  const span = document.createElement('span');
  span.style["left"] = (x * 16) + "px";
  span.style["top"] = (y * 16) + "px";
  span.style["width"] = "16px";
  span.style["height"] = "16px";
  span.style["position"] = "absolute";
  span.style["border"] = "0px";
  span.style["z-index"] = "100";
  span.style["background-color"] = color;
  document.querySelector('#gamemap').appendChild(span);
}

dataPoints = parseDataIntoDataPoints(data);
maxDataPointCount = Math.max(...dataPoints.map(dp => parseInt(dp.count)));
for (const dataPoint of dataPoints) {
  frequencyPercent = dataPoint.count / maxDataPointCount;
  addHeatMapSquare(dataPoint.x, dataPoint.y, getColor(frequencyPercent));
}
