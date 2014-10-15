function createPieChart(container, title, ttipNames, data) {
    function labelf() {
        var point = this.point;
        if (point.name == 'Other') {
            return sprintf('Other: %d items', drilldown.length);
        } else if (!isNaN(point.name)) {
            return sprintf('<b>%s = %s</b>: %s = %s', ttipNames[0], point.name, ttipNames[1], point.y);
        } else {
            return sprintf('<b>%s</b>: %s = %s', point.name, ttipNames[1], point.y);
        }
    }

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
            enabled: false
        },
        series: [
            {
                innerSize: '100%',
                data: data
            }
        ],
        plotOptions: {
            pie: {
                allowPointSelect: true,
                cursor: 'pointer',
                dataLabels: {
                    formatter: labelf
                },
                startAngle: -90,
                endAngle: 90,
                size: '200%',
                center: ['50%', '100%']
            },
            series: {
                point: {
                    events: {
                        click: function () {
                            location.href = this.options.url;
                        }
                    }
                }
            }
        }
    });
}

function createLineChart(container, title, ttipNames, data) {
    if (data[0].name) {
        series = data;
    } else {
        series = [
            { data: data }
        ];
    }

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
                text: ttipNames[0]
            }
        },
        yAxis: {
            title: {
                text: ttipNames[1]
            },
            min: 0
        },
        tooltip: {
            crosshairs: [true, true],
            shared: true,
            formatter: function() {
                var x = this.x;
                try {
                    var label = data.filter(function(p) { return p.x == x; })[0].label;
                } catch (e) {
                    return '';
                }
                if (isNaN(label)) {
                    return sprintf('<b>%s</b>: #%d<br/><b>%s</b>: %s', label, this.x, ttipNames[1], this.y);
                } else {
                    return sprintf('<b>%s = %s</b>: #%d<br/><b>%s</b>: %s', ttipNames[0], label, this.x, ttipNames[1], this.y);
                }
            }
        },
        legend: {
            enabled: !!data[0].name
        },
        plotOptions: {
            series: {
                states: {
                    hover: {
                        lineWidth: 3
                    }
                }
            }
        },
        series: series
    });
}

Highcharts.setOptions({
    lang: {
        drillUpText: '<< Back'
    },
    colors: ["#1F77B4", "#FF7F0E", "#2CA02C", "#D62728", "#9467BD", "#8C564B", "#E377C2", "#7F7F7F", "#BCBD22", "#17BECF"].map(tinycolor).map(function(color) { return color.lighten(10).toRgbString(); })
});
