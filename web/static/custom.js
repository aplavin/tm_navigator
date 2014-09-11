function createPieChart(container, title, ttipNames, cnt, threshold, data) {
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
        plotOptions: {
            pie: {
                allowPointSelect: true,
                cursor: 'pointer',
                dataLabels: {
                    formatter: function() {
                        var point = this.point;
                        if (!isNaN(point.name)) {
                            return sprintf('<b>%s = %s</b>: %.2f %%', ttipNames[0], point.name, point.percentage);
                        } else {
                            return sprintf('<b>%s</b>: %.2f %%', point.name, point.percentage);
                        }
                    }
                }
            }
        },
        drilldown: {
            series: [{
                id: 'smaller',
                data: drilldown
            }]
        }
    });
}

function createLineChart(container, title, ttipNames, data) {
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
        tooltip: {
            headerFormat: '<b>' + ttipNames[0] + ':</b> {point.key}<br/><b>' + ttipNames[1] + ':</b> {point.y}',
            pointFormat: ''
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
                var label = data.filter(function(p) { return p.x == x; })[0].label;
                if (!isNaN(label)) {
                    return sprintf('<b>%s = %s</b>: #%d<br/><b>%s</b>: %s', ttipNames[0], label, this.x, ttipNames[1], this.y);
                } else {
                    return sprintf('<b>%s</b>: #%d<br/><b>%s</b>: %s', label, this.x, ttipNames[1], this.y);
                }
            }
        },
        legend: {
            enabled: false
        },
        series: [
            {
                data: data
            }
        ]
    });
}

function unique(array){
    return array.filter(function(el, index, arr) {
        return index == arr.indexOf(el);
    });
}

function process_data_color(mode) {
    mode = (typeof mode == 'string') ? mode : 'active';

    var backgroundColor = tinycolor('white').darken(5);

    var values = unique($('[data-color]').map(function() { return $(this).data('color'); }).get());
    var colormap = {};
    var colors = Highcharts.getOptions().colors.map(tinycolor);
    values.forEach(function(value, i) {
        colormap[value] = colors[i % colors.length].darken(10);
    });

    var others = {};
    values.forEach(function(value) {
        others[value] = $(sprintf('[data-color=%s] a', value));
    });

    $('[data-color]').each(function() {
        var value = $(this).data('color')
        var color = colormap[value];
        var el = $(this).find('a');

        if (mode == 'active' || mode == 'passive') {
            el.css('background-color', backgroundColor);
            el.css('color', color);
        } else {
            el.css('background-color', $("body").css("background-color"));
            el.css('color', $("body").css("color"));
        }
        if (mode == 'active') {
            el.hover(
                function() {
                    others[value].css('background-color', color.brighten(40));
                    others[value].css('color', 'black');

                    el.css('background-color', color.brighten(10));
                    el.css('color', tinycolor.mostReadable(color, colors));
                }, function() {
                    others[value].css('background-color', backgroundColor);
                    others[value].css('color', color);

                    el.css('background-color', backgroundColor);
                    el.css('color', color);
                }
            );
        } else {
            el.off('mouseenter mouseleave');
        }
    });
}

$(process_data_color);

Highcharts.setOptions({
    lang: {
        drillUpText: '<< Back'
    },
    colors: ["#1F77B4", "#FF7F0E", "#2CA02C", "#D62728", "#9467BD", "#8C564B", "#E377C2", "#7F7F7F", "#BCBD22", "#17BECF"].map(tinycolor).map(function(color) { return color.lighten(10).toRgbString(); })
});
