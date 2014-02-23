
function escape_regexp(str) {
  return str.replace(/[\-\[\]\/\{\}\(\)\*\+\?\.\\\^\$\|]/g, "\\$&");
}

function replace_all(find, replace, str) {
  return str.replace(new RegExp(escape_regexp(find), 'g'), replace);
}

function scroll_down($el) {
    $el.scrollTop($el[0].scrollHeight);
}

function read_log() {
    var $el = $("#log-content");
    var filename = $el.data("filename");

    $.get("/log/read", {"filename": filename}, function (resp) {
        // only scroll down if the scroll is already at the bottom.
        if(($el.scrollTop() + $el.innerHeight()) >= $el[0].scrollHeight) {
            $el.append(resp);
            scroll_down($el);
        } else {
            $el.append(resp);
        }
    });
}

$(document).ready(function() {
    if($("#log-content").length) {
        setInterval(read_log, 1000);
        var $el = $("#log-content");
        scroll_down($el);

        $("#scroll-down-btn").click(function() {
            scroll_down($el);
        })

        $("#search-form").submit(function(e) {
            e.preventDefault();
            var val = $("#search-input").val();
            var $el = $("#log-content");
            var filename = $el.data("filename");
            var params = {
                "filename": filename,
                "text": val
            }

            $.get("/log/search", params, function (resp) {
                $("#logs .controls .status-text").hide();
                $el.find(".found-text").removeClass("found-text");
                if(resp == "0") {
                    var $eof = $("#logs .controls .eof-text");
                    $eof.show();
                    setTimeout(function() {
                        $eof.hide();
                    }, 5000);
                } else {
                    resp = replace_all(params["text"], '<span class="found-text">' + params['text'] + '</span>', resp);
                    $el.html(resp);
                }
            });
        })
    }
});