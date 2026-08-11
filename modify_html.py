import re

with open('frontend/index.html', 'r') as f:
    html = f.read()

# 1. Remove old inline message CSS
html = re.sub(r'\s*\.message \{.*?\n\s*\}', '', html, flags=re.DOTALL)

# 2. Add Modal CSS
css_addition = """
        /* Modal styling */
        .modal-overlay {
            display: none;
            position: fixed;
            top: 0; left: 0; width: 100%; height: 100%;
            z-index: 1000;
            justify-content: center;
            align-items: center;
        }
        .msg-box {
            background-color: #c0c0c0;
            border-top: 2px solid #fff;
            border-left: 2px solid #fff;
            border-right: 2px solid #000;
            border-bottom: 2px solid #000;
            padding: 2px;
            width: 350px;
            box-shadow: 2px 2px 0px rgba(0,0,0,0.5);
        }
        .msg-box-content {
            padding: 20px 10px;
            display: flex;
            flex-direction: column;
            align-items: center;
            text-align: center;
        }
        .msg-icon {
            font-size: 32px;
            margin-bottom: 15px;
        }
"""
html = html.replace('</style>', css_addition + '\n    </style>')

# 3. Remove old inline message HTML
html = re.sub(r'\s*<div id="message" class="message"></div>', '', html)

# 4. Add Modal HTML
html_addition = """
    <!-- Message Box Modal -->
    <div id="msgModal" class="modal-overlay">
        <div class="msg-box">
            <div class="title-bar">
                <div class="title-bar-text" id="msgTitle">Posterity</div>
                <div class="title-bar-controls">
                    <button aria-label="Close" onclick="closeModal()">x</button>
                </div>
            </div>
            <div class="msg-box-content">
                <div id="msgIcon" class="msg-icon">ℹ️</div>
                <p id="msgText" style="margin-bottom: 20px; font-size: 13px; line-height: 1.4;"></p>
                <button onclick="closeModal()" style="width: 80px; padding: 6px;">OK</button>
            </div>
        </div>
    </div>
"""
html = html.replace('</body>', html_addition + '\n</body>')

# 5. Update JS logic
js_helpers = """
        function showModal(title, text, isError) {
            document.getElementById('msgTitle').textContent = title;
            document.getElementById('msgText').textContent = text;
            document.getElementById('msgIcon').textContent = isError ? '❌' : '✅';
            document.getElementById('msgModal').style.display = 'flex';
        }

        function closeModal() {
            document.getElementById('msgModal').style.display = 'none';
        }
"""
html = html.replace('function addResolution() {', js_helpers + '\n        function addResolution() {')

# Replace msgEl logic inside submit listener
html = html.replace("const msgEl = document.getElementById('message');", "")
html = html.replace("msgEl.style.display = 'none';", "")

html = html.replace("msgEl.style.display = 'block';\n                msgEl.textContent = 'Please add at least one resolution.';", "showModal('Error', 'Please add at least one resolution.', true);")
html = html.replace("msgEl.style.display = 'block';\n                msgEl.textContent = 'Plan duration must be longer than check-in frequency.';", "showModal('Error', 'Plan duration must be longer than check-in frequency.', true);")

html = html.replace("msgEl.style.display = 'block';\n                if (res.ok) {\n                    msgEl.textContent = `Time capsule sealed successfully! First check-in: ${data.nextCheckIn}. Plan ends: ${data.endsAt}. Total check-ins: ${data.totalCheckIns}.`;", 
"""if (res.ok) {
                    showModal('Success', `Time capsule sealed successfully! First check-in: ${data.nextCheckIn}. Plan ends: ${data.endsAt}. Total check-ins: ${data.totalCheckIns}.`, false);""")

html = html.replace("} else {\n                    msgEl.textContent = `Error: ${data.error || 'Something went wrong.'}`;\n                }",
"} else {\n                    showModal('Error', data.error || 'Something went wrong.', true);\n                }")

html = html.replace("} catch (err) {\n                msgEl.style.display = 'block';\n                msgEl.textContent = `Network error: ${err.message}`;",
"} catch (err) {\n                showModal('Network Error', err.message, true);")

with open('frontend/index.html', 'w') as f:
    f.write(html)
