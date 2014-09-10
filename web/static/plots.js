function createPlot(container, title, ttipNames, cnt, threshold, data) {
    var cntThresh = data.filter(
        function (point) { return point.y > threshold; }
    ).length;
    cnt = Math.min(cnt, cntThresh);

    if (cnt < data.length) {
        var drilldown = data.slice(cnt);
        var ddown_item = {
            name: 'Other',
            drilldown: 'smaller',
            y: drilldown.reduce(function(total, cur) { return total + cur.y; }, 0)
        };
        data = data.slice(0, cnt).concat([ddown_item]);
    }

    Highcharts.setOptions({
        lang: {
            drillUpText: '<< Back'
        }
    });

    container.highcharts({
        chart: {
            type: 'pie'
        },
        credits: {
            enabled: false
        },
        title: {
            text: title
        },
        tooltip: {
            headerFormat: '<b>' + ttipNames[0] + ':</b> {point.key}<br/><b>' + ttipNames[1] + ':</b> {point.y}',
            pointFormat: ''
        },
        series: [
            {
                data: data
            }
        ],
        drilldown: {
            series: [{
                id: 'smaller',
                data: drilldown
            }]
        }
    });
}
