import re

with open("widget/score.html", "r", encoding="utf-8") as f:
    html = f.read()

debug_script = """<script>
window.onerror = function(msg, url, lineNo, columnNo, error) {
    const err = document.createElement('div');
    err.style.color = 'red';
    err.style.padding = '20px';
    err.style.background = 'black';
    err.style.fontSize = '20px';
    err.style.position = 'fixed';
    err.style.top = '0';
    err.style.zIndex = '999999';
    err.innerHTML = 'JS ERROR: ' + msg + '<br>Line: ' + lineNo;
    document.body.prepend(err);
    return false;
};
window.addEventListener("unhandledrejection", function(e) {
    const err = document.createElement('div');
    err.style.color = 'red';
    err.style.padding = '20px';
    err.style.background = 'black';
    err.style.fontSize = '20px';
    err.style.position = 'fixed';
    err.style.top = '0';
    err.style.zIndex = '999999';
    err.innerHTML = 'PROMISE ERROR: ' + (e.reason ? (e.reason.message || e.reason) : "Unknown Promise Error");
    document.body.prepend(err);
});
</script>
"""

if "window.onerror" not in html:
    html = html.replace("<head>", "<head>\n" + debug_script)
    with open("widget/score.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("Injected debug script into score.html")
