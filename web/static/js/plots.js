function createPieChart(container, title, ttipNames, data, max, showx) {
    container.highcharts({
        chart: {
            type: 'column',
        },
        credits: {
            enabled: false
        },
        legend: {
            enabled: false
        },
        title: {
            text: title
        },
        tooltip: {
            enabled: false
            // formatter: labelf
        },
        xAxis: {
            labels: {
                enabled: showx || 0
            },
            title: {
                text: ttipNames[0]
            },
            categories: data.map(function (it) { return it.name; })
        },
        yAxis: {
            title: {
                text: ttipNames[1]
            },
            max: max || null,
            min: 0
        },
        series: [
            {
                data: data,
                color: '#5bc0de'
            }
        ],
        plotOptions: {
            series: {
                point: {
                    events: {
                        click: function () {
                            location.href = this.options.url;
                        },
                        mouseOver: function () {
                            var name = this.name;
                            var elem = tagcloud.find('a').filter(function () {
                                return $(this).text() == name;
                            });
                            elem.css('font-weight', 'bold');
                        },
                        mouseOut: function () {
                            var name = this.name;
                            var elem = tagcloud.find('a').filter(function () {
                                return $(this).text() == name;
                            });
                            elem.css('font-weight', 'normal');
                        }
                    }
                },
                states: {
                    select: {
                        color: '#eb6864',
                        borderColor: '#eb6864'
                    }
                }
            },
            column: {
                animation: false,
                turboThreshold: 0
            }
        },
    });

    var tagcloud = container.nextAll('.tagcloud:first');

    var hc = container.highcharts();
    tagcloud.find('li').hover(function () {
        hc.series[0].data[$(this).index()].select(true);
    },
    function () {
        hc.series[0].data[$(this).index()].select(false);
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
            },
            enabled: false
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

function process_sparklines() {
    var time = +new Date();
    chunk($('.sparkline').get(), function () {
        if ($(this).data('hlite-tag')) {
            var tagcloud = $(this).next('.tagcloud');
        }
        $(this).highcharts('SparkLine', {
            chart: {
                type: $(this).data('type')
            },
            xAxis: {
                categories: $(this).attr('data-xvals').split(',')
            },
            series: [{
                data: $(this).attr('data-yvals').split(',').map(parseFloat)
            }],
            titles: $(this).data('titles').split(',')
        });
        if ($(this).data('hlite-tag')) {
            var hc = $(this).highcharts();
            tagcloud.find('li').hover(function () {
                hc.series[0].data[$(this).index()].select(true);
            },
            function () {
                hc.series[0].data[$(this).index()].select(false);
            });
        }
    });
}

$(process_sparklines);

$(function () {
    $('.similarity-chart').each(function () {
        var val = parseFloat($(this).data('value'));
        $(this).highcharts('SparkLine', {
            chart: {
                type: 'pie',
                width: 60,
                height: 60,
                style: {
                    width: 40,
                    height: 40
                }
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
