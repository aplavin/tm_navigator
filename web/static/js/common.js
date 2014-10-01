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
