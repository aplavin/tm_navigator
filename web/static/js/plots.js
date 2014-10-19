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

Highcharts.SparkLine = function (options, callback) {
    var defaultOptions = {
        chart: {
            renderTo: (options.chart && options.chart.renderTo) || this,
            backgroundColor: null,
            borderWidth: 0,
            type: 'area',
            margin: [2, 0, 2, 0],
            width: 120,
            height: 40,
            style: {
                overflow: 'visible'
            },
            skipClone: true
        },
        title: {
            text: ''
        },
        credits: {
            enabled: false
        },
        xAxis: {
            labels: {
                enabled: false
            },
            title: {
                text: null
            },
            startOnTick: false,
            endOnTick: false,
            tickPositions: []
        },
        yAxis: {
            endOnTick: false,
            startOnTick: false,
            labels: {
                enabled: false
            },
            title: {
                text: null
            },
            tickPositions: [0]
        },
        legend: {
            enabled: false
        },
        tooltip: {
            backgroundColor: 'white',
            borderWidth: 1,
            shadow: true,
            useHTML: true,
            hideDelay: 0,
            shared: true,
            padding: 0,
            positioner: function (w, h, point) {
                return { x: point.plotX - w / 2, y: point.plotY - h};
            },
            formatter: function labelf() {
                if (!isNaN(this.x)) {
                    return sprintf('<b>%s = %s</b>: %s = %.3f', options.titles[0], this.x, options.titles[1], this.y);
                } else {
                    return sprintf('<b>%s</b>: %s = %.3f', this.x, options.titles[1], this.y);
                }
            }
        },
        plotOptions: {
            series: {
                animation: false,
                lineWidth: 1,
                shadow: false,
                states: {
                    hover: {
                        lineWidth: 1
                    }
                },
                marker: {
                    radius: 1,
                    states: {
                        hover: {
                            radius: 2
                        }
                    }
                },
                fillOpacity: 0.25
            },
            column: {
                negativeColor: '#eb6864',
                borderColor: '#eb6864'
            }
        },
        colors: ['#eb6864']
    };
    options = Highcharts.merge(defaultOptions, options);

    return new Highcharts.Chart(options, callback);
};

$(function () {
    $('.similarity-chart').each(function () {
        var val = parseFloat($(this).data('value'));
        $(this).highcharts('SparkLine', {
            chart: {
                type: 'pie',
                height: 60
            },
            series: [{
                data: [val, 1 - val]
            }],
            colors: ['#eb6864', '#eee'],
            tooltip: {
                enabled: false
            },
            plotOptions: {
                pie: {
                    allowPointSelect: false,
                    dataLabels: {
                        enabled: false
                    }
                },
                series: {
                    states: {
                        hover: {
                            enabled: false
                        }
                    }
                }
            }
        });
        $(this).attr('title', sprintf('Similarity: %d%%', val * 100));
    });
})

Highcharts.setOptions({
    lang: {
        drillUpText: '<< Back'
    },
    colors: ["#1F77B4", "#FF7F0E", "#2CA02C", "#D62728", "#9467BD", "#8C564B", "#E377C2", "#7F7F7F", "#BCBD22", "#17BECF"].map(tinycolor).map(function(color) { return color.lighten(10).toRgbString(); })
});
