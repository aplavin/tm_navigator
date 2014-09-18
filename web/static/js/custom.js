function createPieChart(container, title, ttipNames, cnt, threshold, data) {
    var cntThresh = data.filter(
        function (point) { return point.y > threshold; }
    ).length;
    cnt = Math.min(cnt, cntThresh);

    if (cnt < data.length - 3) {
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
            headerFormat: sprintf('<b>%s:</b> {point.key}<br/><b>%s:</b> {point.y}', ttipNames[0], ttipNames[1]),
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
                            return sprintf('<b>%s = %s</b>: %s = %s', ttipNames[0], point.name, ttipNames[1], point.y);
                        } else {
                            return sprintf('<b>%s</b>: %s = %s', point.name, ttipNames[1], point.y);
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
    if (!data[0].name) {
        series = [ { data: data }];
    } else {
        series = data;
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
            enabled: !!data[0].name
        },
        plotOptions: {
            series: {
                states: {
                    hover: {
                        lineWidth: 2
                    }
                }
            }
        },
        series: series
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
        if (i >= colors.length - 1) {
            i = colors.length - 1;
        }
        colormap[value] = colors[i].darken(10);
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

function process_tagclouds() {
    $('.tagcloud:visible').each(function process_tagcloud() {
        var elems = $(this).find('a');
        var sizes = elems.map(function get_datasize() { return $(this).data('size'); }).get();
        var max = Math.max.apply(null, sizes);
        elems.each(function setsize() {
            var val = $(this).data('size');
            var relval = Math.max(Math.sqrt(val / max), 0.2);
            $(this).fadeTo(0, relval);
            if (relval > 0.8) {
                $(this).css('font-weight', 'bold');
            }
            // $(this).css('font-size', relval + 'em');
        });
    });
}

$(process_tagclouds);

function fill_table(table, dataset, limit) {
    var tbody = $(table).find('tbody');
    tbody.empty();

    function show_data(data) {
        data.forEach(function (row, i) {
            var trow = $('<tr></tr>');
            tbody.append(trow);
            dataset['columns'].forEach(function (col) {
                var tcell = $('<td></td>');
                switch (col['type']) {
                    case 'index':
                        tcell.append(i + 1);
                        break;
                    case 'text':
                        tcell.append(row[col['field']]);
                        break;
                    case 'link':
                        var a = $('<a></a>');
                        a.attr('href', sprintf(col['href_fmt'], row[col['href_field']]));
                        a.text(row[col['text_field']]);
                        tcell.append(a);
                        break;
                    case 'tagcloud':
                        var ul = $('<ul></ul>');
                        ul.addClass('tagcloud');
                        row[col['field']].forEach(function (val) {
                            var li = $('<li></li>');
                            var a = $('<a></a>');
                            a.data('size', val[col['size_field']]);
                            a.attr('href', sprintf(col['href_fmt'], val[col['href_field']]));
                            a.text(val[col['text_field']]);
                            li.append(a);
                            ul.append(li);
                            ul.append('\n');
                        });
                        tcell.append(ul);
                        break;
                }
                trow.append(tcell);
            });
        })
    }

    show_data(dataset['data'].slice(0, limit));
    process_tagclouds();

    var input_div = $('<div></div>');
    input_div.addClass('filter-input');
    var input = $('<input type="text" placeholder="enter search terms..." />');
    input.attr('id', 'filter-input');
    input_div.append('<label>Search:</label>');
    input_div.append(input);
    $(table).before(input_div);

    $(input).on('input', function() {
        var search = $(this).val();
        var regexp = new RegExp(search, 'i');
        var found = [];
        dataset['data'].every(function (row, ri) {
            var cur_matches = [];
            traverse(row).forEach(function (obj) {
                if (typeof obj == 'string' && regexp.exec(obj)) {
                    cur_matches.push([this.path, obj]);
                }
            });
            if (cur_matches.length > 0) {
                found.push([ri, cur_matches]);
            }
            return found.length < limit;
        });
        tbody.empty();
        var data = [];
        found.forEach(function (fobj) {
            var ri = fobj[0];
            data.push(dataset['data'][ri]);
        });
        show_data(data);
    });
}

$(function () {
    $('.overlay-container').each(function () {
        var divs = $(this).find('div');
        var base = divs[0];
        var overlay = divs[1];
        $(this).hover(
            function () {
                $(overlay).slideUp('slow');
            },
            function () {
                $(overlay).slideDown('slow');
            }
        );
    });
});

$(function(){
    var header = $('.sticky-header');
    var replacement = $('<div></div>');
    header.after(replacement);

    var stickyHeaderTop = null;

    $(window).scroll(function(){
        if (!header.is(':visible')) {
            return;
        }
        if (stickyHeaderTop === null) {
            stickyHeaderTop = header.offset().top;
            return;
        }

        if ($(window).scrollTop() > stickyHeaderTop) {
            replacement.css('height', header.css('height'));
            header.css({
                position: 'fixed',
                top: '0px',
                right: '0px',
                opacity: '0.9'
            });
        } else {
            replacement.css('height', '0');
            header.css({
                position: 'static',
                opacity: '1'
            });
        }
    });
  });
