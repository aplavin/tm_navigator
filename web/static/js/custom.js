function createPieChart(container, title, ttipNames, data) {
    var cnt = 15;
    // var threshold = 0.01;

    // var total = data.reduce(function(total, cur) { return total + cur.y; }, 0);
    // var cntThresh = data.filter(
    //     function (point) { return point.y / total > threshold; }
    // ).length;
    // cnt = Math.min(cnt, cntThresh);

    if (cnt < data.length - 3) {
        var drilldown = data.slice(cnt);
        var ddown_item = {
            name: 'Other',
            drilldown: 'smaller',
            y: drilldown.reduce(function(total, cur) { return total + cur.y; }, 0)
        };
        data = data.slice(0, cnt).concat([ddown_item]);
    }

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
            formatter: labelf,
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
                    formatter: labelf
                }
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

function unique(array){
    return array.filter(function(el, index, arr) {
        return index == arr.indexOf(el);
    });
}

function process_data_color(mode) {
    if (typeof mode != 'string') {
        mode = 'active';
    }

    var backgroundColor = tinycolor('white').darken(5);
    backgroundColor.setAlpha(0.7);

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
        var value = $(this).data('color');
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
    $('.tagcloud').each(function process_tagcloud() {
        var valprefix = $(this).data('valprefix');
        var elems = $(this).find('a');
        var sizes = elems.map(function get_datasize() { return $(this).data('size'); }).get();
        var max = Math.max.apply(null, sizes);
        elems.each(function setsize() {
            var val = $(this).data('size');
            if (valprefix) {
                $(this).attr('title', valprefix + val)
            }
            var relval = Math.max(Math.sqrt(val / max), 0.3);
            $(this).css('opacity', relval);
            // if (relval > 0.8) {
            //     $(this).css('font-weight', 'bold');
            // }
            // $(this).css('font-size', relval + 'em');
        });
    });
}

$(process_tagclouds);

function fill_table(table, dataset, limit) {
    if (!limit) {
        limit = dataset.data.length;
    }
    var tbody = $(table).find('tbody');
    tbody.empty();

    function show_data(data) {
        data.forEach(function (row, i) {
            var trow = $('<tr></tr>');
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
                        var ul = $('<ul>');
                        ul.addClass('tagcloud');
                        if (col['valprefix']) {
                            ul.attr('data-valprefix', col['valprefix']);
                        }
                        row[col['field']].forEach(function (val) {
                            var li = $('<li>');
                            var a = $('<a>',{
                                'data-size': val[col['size_field']],
                                'href': sprintf(col['href_fmt'], val[col['href_field']]),
                                'text': val[col['text_field']]
                            });
                            // a.data('size', val[col['size_field']]);
                            // a.attr('href', sprintf(col['href_fmt'], val[col['href_field']]));
                            // a.text(val[col['text_field']]);
                            li.append(a);
                            ul.append(li);
                            ul.append('\n');
                        });
                        tcell.append(ul);
                        break;
                }
                trow.append(tcell);
            });
            tbody.append(trow);
        })
    }

    show_data(dataset['data'].slice(0, limit));
    process_tagclouds();

    var input_div = $('<div>', {
        'class': 'form-horizontal'
    }).append($('<div>', {
        'class': 'has-feedback'
    }).append(input = $('<input>', {
        'type': 'text',
        'class': 'form-control',
        'id': 'filter-input',
        'placeholder': 'Search'
    })).append($('<span>', {
        'class': 'form-control-feedback glyphicon glyphicon-search'
    })));
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
        process_tagclouds();
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


$(function () {
    $('.collapsed').each(function () {
        var collapsed = $(this);

        var cnt_hidden = collapsed.children().filter(function () {
            return $(this).position().top - collapsed.position().top >= collapsed.height();
        }).length;

        if (cnt_hidden == 0) {
            return;
        }

        collapsed.removeClass('collapsed');
        var height = collapsed.height();
        collapsed.addClass('collapsed');

        var a = $('<a></a>');
        a.attr('href', '#');
        a.addClass('text-muted');
        collapsed.before(a);

        var a_icon = $('<span></span>');
        a_icon.addClass('glyphicon glyphicon-expand');
        a.append(a_icon);

        a.append('&nbsp;');

        var a_text = $('<span></span>');
        a_text.text(sprintf('Show %d more', cnt_hidden));
        a.append(a_text);

        a.click(function (evt) {
            evt.preventDefault();
            if (a_text.text() == 'Less') {
                collapsed.css('max-height', '');
                a_text.text(sprintf('Show %d more', cnt_hidden));
                a_icon.addClass('glyphicon-expand');
                a_icon.removeClass('glyphicon-collapse-down');
            } else {
                collapsed.css('max-height', height);
                a_text.text('Less');
                a_icon.removeClass('glyphicon-expand');
                a_icon.addClass('glyphicon-collapse-down');
            }
        });
    });
});


$(function () {
    $('[data-collapsed]').each(function () {
        var elem = $(this);
        elem.hide();

        var a = $('<a></a>');
        a.attr('href', '#');
        a.addClass('text-muted');
        elem.before(a);

        var a_icon = $('<span></span>');
        a_icon.addClass('glyphicon glyphicon-expand');
        a.append(a_icon);

        a.append('&nbsp;');

        var a_text = $('<span></span>');
        a_text.text(elem.data('collapse-label'));
        a.append(a_text);

        a.click(function (evt) {
            evt.preventDefault();
            if (elem.is(':visible')) {
                elem.hide();
                a_icon.addClass('glyphicon-expand');
                a_icon.removeClass('glyphicon-collapse-down');
            } else {
                elem.show();
                a_icon.removeClass('glyphicon-expand');
                a_icon.addClass('glyphicon-collapse-down');
            }
        });
    });
});


// Add an URL parser to JQuery that returns an object
// This function is meant to be used with an URL like the window.location
// Use: $.parseParams('http://mysite.com/?var=string') or $.parseParams() to parse the window.location
// Simple variable:  ?var=abc                        returns {var: "abc"}
// Simple object:    ?var.length=2&var.scope=123     returns {var: {length: "2", scope: "123"}}
// Simple array:     ?var[]=0&var[]=9                returns {var: ["0", "9"]}
// Array with index: ?var[0]=0&var[1]=9              returns {var: ["0", "9"]}
// Nested objects:   ?my.var.is.here=5               returns {my: {var: {is: {here: "5"}}}}
// All together:     ?var=a&my.var[]=b&my.cookie=no  returns {var: "a", my: {var: ["b"], cookie: "no"}}
// You just cant have an object in an array, ?var[1].test=abc DOES NOT WORK
(function ($) {
    var re = /([^&=]+)=?([^&]*)/g;
    var decode = function (str) {
        return decodeURIComponent(str.replace(/\+/g, ' '));
    };
    $.parseParams = function (query) {
        // recursive function to construct the result object
        function createElement(params, key, value) {
            key = key + '';
            // if the key is a property
            if (key.indexOf('.') !== -1) {
                // extract the first part with the name of the object
                var list = key.split('.');
                // the rest of the key
                var new_key = key.split(/\.(.+)?/)[1];
                // create the object if it doesnt exist
                if (!params[list[0]]) params[list[0]] = {};
                // if the key is not empty, create it in the object
                if (new_key !== '') {
                    createElement(params[list[0]], new_key, value);
                } else console.warn('parseParams :: empty property in key "' + key + '"');
            } else
            // if the key is an array
            if (key.indexOf('[') !== -1) {
                // extract the array name
                var list = key.split('[');
                key = list[0];
                // extract the index of the array
                var list = list[1].split(']');
                var index = list[0]
                // if index is empty, just push the value at the end of the array
                if (index == '') {
                    if (!params) params = {};
                    if (!params[key] || !$.isArray(params[key])) params[key] = [];
                    params[key].push(value);
                } else
                // add the value at the index (must be an integer)
                {
                    if (!params) params = {};
                    if (!params[key] || !$.isArray(params[key])) params[key] = [];
                    params[key][parseInt(index)] = value;
                }
            } else
            // just normal key
            {
                if (!params) params = {};
                params[key] = value;
            }
        }
        if (!query) query = window.location + '';
        var params = {}, e;
        if (query) {
            // remove # from end of query
            if (query.indexOf('#') !== -1) {
                query = query.substr(0, query.indexOf('#'));
            }

            // remove ? at the begining of the query
            if (query.indexOf('?') !== -1) {
                query = query.substr(query.indexOf('?') + 1, query.length);
            } else return {};
            // empty parameters
            if (query == '') return {};
            // execute a createElement on every key and value
            while (e = re.exec(query)) {
                var key = decode(e[1]);
                var value = decode(e[2]);
                createElement(params, key, value);
            }
        }
        return params;
    };
})(jQuery);

function search(new_args) {
    $('#search-loading').show();
    $('#search-error').hide();

    var args = $.parseParams();
    if (new_args) {
        for (var name in new_args) {
            if (new_args[name]) {
                args[name] = new_args[name];
            } else {
                delete args[name];
            }
        }
    }
    search_settings_display_from_args(args);

    $.ajax({
        url: sprintf($('#search-input').data('search-base-url'), $('#search-input').val().replace('/', ' ')),
        data: args,
        dataType: 'html'
    }).success(function (data) {
        $('#search-results').html(data);
        process_tagclouds();
        $('[data-toggle=tooltip]').tooltip();
    }).error(function (xhr, type, exception) {
        $('#search-error').show();
    }).complete(function () {
        $('#search-loading').hide();
        var new_url = this.url.replace('/search_results/', '/search/');
        if (window.location.href != new_url) {
            window.history.pushState(null, null, new_url);
        }
    });
}

function search_settings_display_from_args(args) {
    $('a[data-switch-name]').each(function () {
        if (args[$(this).data('switch-name')]) {
            $(this).data('switch-selected', true);
            $(this).removeClass('btn-default').addClass('btn-primary');
            $(this).find('span:first-child').text('on');
        } else {
            $(this).data('switch-selected', false);
            $(this).removeClass('btn-primary').addClass('btn-default');
            $(this).find('span:first-child').text('off');
        }
    });
    $('div[data-switch-name]').each(function () {
        if (args[$(this).data('switch-name')]) {
            $(this).data('switch-selected', args[$(this).data('switch-name')]);
            $(this).find('button').removeClass('btn-default').addClass('btn-primary');
        } else {
            $(this).data('switch-selected', '');
            $(this).find('button').removeClass('btn-primary').addClass('btn-default');
        }
        var text = $(this).find(sprintf('[data-switch-value="%s"]', $(this).data('switch-selected'))).text();
        $(this).find('button span:first-child').text(text);
    });
}

$(function () {
    var args = $.parseParams();
    search_settings_display_from_args(args);
})

function init_search() {
    $('a[data-switch-name]').each(function () {
        var name = $(this).data('switch-name');
        $(this).on('click', function (evt) {
            evt.preventDefault();

            var enabled = $(this).data('switch-selected');
            $(this).data('switch-selected', !enabled);
            var args = Object();
            args[name] = !enabled;
            search(args);
        });
    });
    $('div[data-switch-name]').each(function () {
        var elem = $(this);
        var name = $(this).data('switch-name');
        $(this).find('ul li a').click(function (evt) {
            evt.preventDefault();

            var selected = $(this).data('switch-value');
            elem.data('switch-selected', selected);
            var args = Object();
            args[name] = selected;
            search(args);
        });
    });
    $('#search-input').on('input', function () { search(); });
}

$(function () {
    $('[data-toggle=tooltip]').tooltip();
})


$(function () {
    $('#content h1 br').replaceWith(' ');
});
