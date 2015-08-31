function send_value(element, url, parameters, value) {
    parameters['value'] = value;
    $.ajax({
        url: url,
        type: 'POST',
        data: JSON.stringify(parameters),
        contentType: "application/json",
        complete: function (xhr, status) {
            var categories = {
                success: 'success',
                notmodified: 'info',
                nocontent: 'info',
                error: 'error',
                timeout: 'warning',
                abort: 'error',
                parsererror: 'error',
            }
            element.notify(status, categories[status]);
        }
    });
}

function yesno_handler(flag) {
    function click_handler() {
        var block = $(this).parent('.assess-yesno');
        var url = block.data('url');
        var parameters = block.data('parameters').replace(/'/g, '"');
        parameters = JSON.parse(parameters);
        var value = flag ? +1 : -1;

        if (confirm('Send assessment?')) {
            send_value(block, url, parameters, value);
        }
    }

    return click_handler;
}

$(document).on('click', '.assess-yesno button:first-of-type', yesno_handler(true));
$(document).on('click', '.assess-yesno button:last-of-type', yesno_handler(false));
