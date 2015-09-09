function send_value(element, url, value) {
    $.ajax({
        url: url,
        type: 'POST',
        data: {value: value},
        contentType: "application/x-www-form-urlencoded",
        complete: function (xhr, status) {
            var categories = {
                success: 'success',
                notmodified: 'info',
                nocontent: 'info',
                error: 'error',
                timeout: 'warning',
                abort: 'error',
                parsererror: 'error',
            };
            element.notify(status, categories[status]);
        }
    });
}

function yesno_handler(flag) {
    function click_handler() {
        var block = $(this).parent('.assess-yesno');
        var url = block.data('url');
        var value = flag ? +1 : -1;

        if (confirm('Send assessment?')) {
            send_value(block, url, value);
        }
    }

    return click_handler;
}

$(document).on('click', '.assess-yesno button:first-of-type', yesno_handler(true));
$(document).on('click', '.assess-yesno button:last-of-type', yesno_handler(false));
