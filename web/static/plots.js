function createPlot(container, title, xTitle, xCats, yTitle, ttipNames, data) {
    container.highcharts({
        chart: {
            type: 'line'
        },
        credits: {
            enabled: false
        },
        title: {
            text: title
        },
        xAxis: {
            title: {
                text: xTitle
            },
            labels: {
                enabled: false
            },
            tickLength: 0,
            categories: xCats
        },
        yAxis: {
            title: {
                text: yTitle
            },
            floor: 0
        },
        tooltip: {
            headerFormat: '<b>' + ttipNames[0] + ':</b> {point.x}<br/><b>' + ttipNames[1] + ':</b> {point.y}',
            pointFormat: '',
            shared: true,
            crosshairs: [true, true]
        },
        series: [
            {
                showInLegend: false,
                data: data
            }
        ]
    });
}
