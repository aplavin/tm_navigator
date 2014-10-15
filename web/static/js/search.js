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
        $('#search-results').fadeIn(200);
        process_tagclouds();
        $('[data-toggle=tooltip]').tooltip({ container: 'body' });
    }).error(function (xhr, type, exception) {
        $('#search-error').show();
    }).complete(function () {
        $('#search-loading').fadeOut();
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
});

var search_timer;

function trigger_search(delay, args) {
    $('#search-results').fadeOut(500);
    $('#search-loading').fadeIn(200);
    $('#search-error').hide();
    clearTimeout(search_timer);
    search_timer = setTimeout(function () { search(args); }, delay);
}

function init_search() {
    $('a[data-switch-name]').each(function () {
        var name = $(this).data('switch-name');
        $(this).on('click', function (evt) {
            evt.preventDefault();

            var enabled = $(this).data('switch-selected');
            $(this).data('switch-selected', !enabled);
            var args = Object();
            args[name] = !enabled;

            trigger_search(0, args);
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

            trigger_search(0, args);
        });
    });

    $('#search-input').on('input', function () {
        trigger_search(1000);
    });

    $('#search-input').autocomplete({
        serviceUrl: $('#search-input').data('search-completions-url'),
        minChars: 0,
        delimiter: ' ',
        maxHeight: 1000,
        triggerSelectOnValidInput: false
    });
};
