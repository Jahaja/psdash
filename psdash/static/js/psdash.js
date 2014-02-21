

$(document).ready(function() {
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

    if($("#log-content").length) {
        setInterval(read_log, 1000);
        var $el = $("#log-content");
        scroll_down($el);

        $("#scroll-down-btn").click(function() {
            scroll_down($el);
        })

        $("#search-form").submit(function(e) {
            e.preventDefault();
            var $el = $("#log-content");
            var filename = $el.data("filename");
            var params = {
                "filename": filename,
                "text": $("#search-input").val()
            }

            $.get("/log/search", params, function (resp) {
                $el.text(resp);
            });
        })
    }
});