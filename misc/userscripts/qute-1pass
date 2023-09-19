#!/usr/bin/env bash

set +e

# JS field injection code from https://github.com/qutebrowser/qutebrowser/blob/main/misc/userscripts/password_fill
javascript_escape() {
    # print the first argument in an escaped way, such that it can safely
    # be used within javascripts double quotes
    # shellcheck disable=SC2001
    sed "s,[\\\\'\"\/],\\\\&,g" <<< "$1"
}

js() {
cat <<EOF
    function isVisible(elem) {
        var style = elem.ownerDocument.defaultView.getComputedStyle(elem, null);
        if (style.getPropertyValue("visibility") !== "visible" ||
            style.getPropertyValue("display") === "none" ||
            style.getPropertyValue("opacity") === "0") {
            return false;
        }
        return elem.offsetWidth > 0 && elem.offsetHeight > 0;
    };
    function hasPasswordField(form) {
        var inputs = form.getElementsByTagName("input");
        for (var j = 0; j < inputs.length; j++) {
            var input = inputs[j];
            if (input.type == "password") {
                return true;
            }
        }
        return false;
    };
    function loadData2Form (form) {
        var inputs = form.getElementsByTagName("input");
        for (var j = 0; j < inputs.length; j++) {
            var input = inputs[j];
            if (isVisible(input) && (input.type == "text" || input.type == "email")) {
                input.focus();
                input.value = "$(javascript_escape "${USERNAME}")";
                input.dispatchEvent(new Event('change'));
                input.blur();
            }
            if (input.type == "password") {
                input.focus();
                input.value = "$(javascript_escape "${PASSWORD}")";
                input.dispatchEvent(new Event('change'));
                input.blur();
            }
        }
    };
    var forms = document.getElementsByTagName("form");
    if("$(javascript_escape "${QUTE_URL}")" == window.location.href) {
        for (i = 0; i < forms.length; i++) {
            if (hasPasswordField(forms[i])) {
                loadData2Form(forms[i]);
            }
        }
    } else {
        alert("Secrets will not be inserted.\nUrl of this page and the one where the user script was started differ.");
    }
EOF
}

URL=$(echo "$QUTE_URL" | awk -F/ '{print $3}' | sed 's/www.//g')
TOKEN_TMPDIR="${TMPDIR:-/tmp}"
TOKEN_CACHE="$TOKEN_TMPDIR/1pass.token"

echo "message-info 'Looking for password for $URL...'" >> "$QUTE_FIFO"

if [ -f "$TOKEN_CACHE" ]; then
    TOKEN=$(cat "$TOKEN_CACHE")
    if ! op signin --session="$TOKEN" --output=raw > /dev/null; then
        TOKEN=$(rofi -dmenu -password -p "1password: "| op signin --output=raw) || TOKEN=""
        echo "$TOKEN" > "$TOKEN_CACHE"
    fi
else
    TOKEN=$(rofi -dmenu -password -p "1password: "| op signin --output=raw) || TOKEN=""
    install -m 600 /dev/null "$TOKEN_CACHE"
    echo "$TOKEN" > "$TOKEN_CACHE"
fi


if [ -n "$TOKEN" ]; then
    UUID=$(op list items --cache --session="$TOKEN" | jq --arg url "$URL" -r '[.[] | {uuid, url: [.overview.URLs[]?.u, .overview.url][]?} | select(.uuid != null) | select(.url != null) | select(.url|test(".*\($url).*"))][.0].uuid') || UUID="" 

    if [ -z "$UUID" ] || [ "$UUID" == "null" ];then
        echo "message-error 'No entry found for $URL'" >> "$QUTE_FIFO"
        TITLE=$(op list items --cache --session="$TOKEN" | jq -r '.[].overview.title' | rofi -dmenu -i) || TITLE=""
        if [ -n "$TITLE" ]; then
            UUID=$(op list items --cache --session="$TOKEN" | jq --arg title "$TITLE" -r '[.[] | {uuid, title:.overview.title}|select(.title|test("\($title)"))][.0].uuid') || UUID=""
        else
            UUID=""
        fi
    fi

    if [ -n "$UUID" ];then
        ITEM=$(op get item --cache --session="$TOKEN" "$UUID")

        PASSWORD=$(echo "$ITEM" | jq -r '.details.fields | .[] | select(.designation=="password") | .value')

        if [ -n "$PASSWORD" ]; then
            TITLE=$(echo "$ITEM" | jq -r '.overview.title')
            USERNAME=$(echo "$ITEM" | jq -r '.details.fields | .[] | select(.designation=="username") | .value')

            printjs() {
                js | sed 's,//.*$,,' | tr '\n' ' '
            }
            echo "jseval -q $(printjs)" >> "$QUTE_FIFO"

            TOTP=$(echo "$ITEM" | op get totp --cache --session="$TOKEN" "$UUID") || TOTP=""
            if [ -n "$TOTP" ]; then
                echo "$TOTP" | xclip -in -selection clipboard
                echo "message-info 'Pasted one time password for $TITLE to clipboard'" >> "$QUTE_FIFO" 
            fi
        else
            echo "message-error 'No password found for $URL'" >> "$QUTE_FIFO"
        fi
    else
        echo "message-error 'Entry not found for $UUID'" >> "$QUTE_FIFO"
    fi
else
    echo "message-error 'Wrong master password'" >> "$QUTE_FIFO"
fi
