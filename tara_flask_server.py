from flask import Flask, render_template_string

app = Flask(__name__)

HTML = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Tara Bot - Invite & Info</title>
    <!-- Fonts: Orbitron for body, Pacifico for Tara Bot -->
    <link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@700&family=Roboto:wght@400;700&family=Pacifico&display=swap" rel="stylesheet">
    <style>
        /* Rainbow cursor follower */
        .rainbow-cursor {
            position: fixed;
            top: 0; left: 0;
            width: 60px;
            height: 60px;
            pointer-events: none;
            border-radius: 50%;
            opacity: 0.5;
            z-index: 9999;
            background: conic-gradient(
                #ff00cc, #3333ff, #00ffcc, #ffcc00, #ff00cc
            );
            filter: blur(8px);
            transition: background 0.5s;
            animation: rainbow-cursor-anim 3s linear infinite;
        }
        @keyframes rainbow-cursor-anim {
            0% { filter: blur(8px) hue-rotate(0deg); }
            100% { filter: blur(8px) hue-rotate(360deg); }
        }
        html, body {
            height: 100%;
            margin: 0;
            padding: 0;
        }
        body {
            min-height: 100vh;
            min-width: 100vw;
            width: 100vw;
            height: 100vh;
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            background: linear-gradient(135deg, #232526 0%, #414345 100%);
            color: #fff;
            font-family: 'Orbitron', Arial, sans-serif;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .container {
            background: rgba(30, 30, 40, 0.97);
            box-shadow: 0 0 0 0 rgba(31, 38, 135, 0.0);
            padding: 0;
            width: 100vw;
            height: 100vh;
            min-height: 100vh;
            min-width: 100vw;
            text-align: center;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            overflow: hidden;
        }
        .dashboard-content {
            position: relative;
            background: rgba(30, 30, 40, 0.97);
            border-radius: 32px;
            box-shadow: 0 12px 48px 0 rgba(31, 38, 135, 0.37);
            padding: 60px 50px 40px 50px;
            max-width: 700px;
            width: 90vw;
            min-width: 320px;
            min-height: 400px;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            z-index: 1;
        }
        /* Remove old dashboard-content::before and hover effect */
        @keyframes rainbow-border {
            0% { background-position: 0% 50%; }
            50% { background-position: 100% 50%; }
            100% { background-position: 0% 50%; }
        }
        .tara-title {
            font-family: 'Pacifico', cursive;
            font-size: 3.2rem;
            margin-bottom: 10px;
            letter-spacing: 2px;
            color: #ffb6c1;
            text-shadow: 0 2px 16px #ff69b4, 0 1px 0 #fff;
        }
        p {
            font-size: 1.25rem;
            margin-bottom: 36px;
            color: #e0e0e0;
        }
        .invite-btn {
            display: inline-block;
            background: linear-gradient(90deg, #ffb6c1 0%, #ff69b4 100%);
            color: #232526;
            font-weight: bold;
            padding: 18px 40px;
            border-radius: 40px;
            font-size: 1.35rem;
            text-decoration: none;
            box-shadow: 0 4px 24px rgba(255, 182, 193, 0.25);
            transition: background 0.3s, color 0.3s, transform 0.2s;
        }
        .invite-btn:hover {
            background: linear-gradient(90deg, #ff69b4 0%, #ffb6c1 100%);
            color: #fff;
            transform: scale(1.07);
        }
        .footer {
            margin-top: 40px;
            font-size: 1.05rem;
            color: #aaa;
        }
        @media (max-width: 600px) {
            .container {
                padding: 30px 10px 20px 10px;
                max-width: 98vw;
            }
            .tara-title {
                font-size: 2.1rem;
            }
            .invite-btn {
                font-size: 1.05rem;
                padding: 12px 18px;
            }
        }
    </style>
    </style>
    <script>
        document.addEventListener('DOMContentLoaded', function() {
            const cursor = document.createElement('div');
            cursor.className = 'rainbow-cursor';
            document.body.appendChild(cursor);
            let mouseX = window.innerWidth / 2, mouseY = window.innerHeight / 2;
            let currentX = mouseX, currentY = mouseY;
            document.addEventListener('mousemove', function(e) {
                mouseX = e.clientX;
                mouseY = e.clientY;
            });
            function animate() {
                currentX += (mouseX - currentX) * 0.18;
                currentY += (mouseY - currentY) * 0.18;
                cursor.style.transform = `translate(-50%, -50%) translate(${currentX}px, ${currentY}px)`;
                requestAnimationFrame(animate);
            }
            animate();
        });
    </script>
</head>
<body>
    <div class="container">
        <div class="dashboard-content">
            <div class="tara-title">Tara Bot</div>
            <p>Your all-in-one Discord AI assistant.<br>Invite Tara to your server and experience the future of chat, images, and voice!</p>
            <a class="invite-btn" href="https://discord.com/oauth2/authorize?client_id=1400843949278626035&permissions=1071660915520&integration_type=0&scope=bot+applications.commands" target="_blank">Invite Tara Bot</a>
            <div class="footer">Made with <span style="color:#ffb6c1">♥</span> by Manish | Powered by OpenAI</div>
        </div>
    </div>
</body>
</html>
'''

@app.route("/")
def home():
    return render_template_string(HTML)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
