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

function assess_handler(value) {
    function click_handler() {
        var block = $(this).parent('.assess-yesno');
        var url = block.data('url');

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


$(document).on('click', '.assess-yesno button:nth-of-type(1)', yesno_handler(true));
$(document).on('click', '.assess-yesno button:nth-of-type(2)', yesno_handler(false));

$(document).on('click', '.assess-topic button:nth-of-type(1)', assess_handler(1));
$(document).on('click', '.assess-topic button:nth-of-type(2)', assess_handler(2));
$(document).on('click', '.assess-topic button:nth-of-type(3)', assess_handler(3));
$(document).on('click', '.assess-topic button:nth-of-type(4)', assess_handler(4));
$(document).on('click', '.assess-topic button:nth-of-type(5)', assess_handler(5));
