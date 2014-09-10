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

function unique(array){
    return array.filter(function(el, index, arr) {
        return index == arr.indexOf(el);
    });
}

function process_data_color(alpha) {
    alpha = (typeof alpha == 'number') ? alpha : 0.3;

    var values = unique($('[data-color]').map(function() { return $(this).data('color'); }).get());
    var colormap = {};
    var colors = Highcharts.getOptions().colors.map(tinycolor);
    values.forEach(function(value, i) {
        colormap[value] = tinycolor(colors[i % colors.length].toRgb());
        colormap[value].setAlpha(alpha / Math.pow(i / colors.length, 0.3));
    });
    console.log(colors);

    $('[data-color]').each(function() {
        var background = colormap[$(this).data('color')]
        $(this).css('background-color', background.toRgbString());
        $(this).find('*').css('color', tinycolor.mostReadable(background, colors));
    });
}

$(process_data_color);
