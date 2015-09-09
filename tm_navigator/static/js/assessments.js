function send_value(element, url, value) {
    $.ajax({
        url: url,
        type: 'POST',
        data: {value: value},
        contentType: "application/x-www-form-urlencoded",
        complete: function (xhr, status) {
            var texts = {
                success: 'Your assessment was successfully saved.',
                notmodified: 'Unknown situation, please report it!',
                nocontent: 'Unknown situation, please report it!',
                error: 'An error occurred, assessment is not saved!',
                timeout: 'An error occurred, assessment is not saved!',
                abort: 'An error occurred, assessment is not saved!',
                parsererror: 'An error occurred, assessment is not saved!',
            };
            bootbox.alert(sprintf('<h4>%s</h4>Server responded: %s' ,texts[status], status));
        }
    });
}

function yesno_handler(flag) {
    function click_handler() {
        var block = $(this).parent('.assess-yesno');
        var url = block.data('url');
        var value = flag ? +1 : -1;

        var question = $(this).siblings('span').eq(0).text();
        var answer = $(this).attr('title');
        bootbox.confirm(sprintf('<h4>Send assessment?</h4>%s - %s', question, answer), function (response) {
            if (response) {
                send_value(block, url, value);
            }
        });
    }

    return click_handler;
}

$(document).on('click', '.assess-yesno button:first-of-type', yesno_handler(true));
$(document).on('click', '.assess-yesno button:last-of-type', yesno_handler(false));
