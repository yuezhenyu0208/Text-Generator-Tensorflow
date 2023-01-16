'''

This is a library for formatting GPT-4chan and chat outputs as nice HTML.

'''

import re
from pathlib import Path

def generate_basic_html(s):
    s = '\n'.join([f'<p style="margin-bottom: 20px">{line}</p>' for line in s.split('\n')])
    s = f'<div style="max-width: 600px; margin-left: auto; margin-right: auto; background-color:#efefef; color:#0b0f19; padding:3em; font-size:1.1em; font-family: helvetica">{s}</div>'
    return s

def process_post(post, c):
    t = post.split('\n')
    number = t[0].split(' ')[1]
    if len(t) > 1:
        src = '\n'.join(t[1:])
    else:
        src = ''
    src = re.sub('>', '&gt;', src)
    src = re.sub('(&gt;&gt;[0-9]*)', '<span class="quote">\\1</span>', src)
    src = re.sub('\n', '<br>\n', src)
    src = f'<blockquote class="message">{src}\n'
    src = f'<span class="name">Anonymous </span> <span class="number">No.{number}</span>\n{src}'
    return src

def generate_4chan_html(f):
    css = """
    #container {
        background-color: #eef2ff;
        padding: 17px;
    }
    .reply {
        background-color: rgb(214, 218, 240);
        border-bottom-color: rgb(183, 197, 217);
        border-bottom-style: solid;
        border-bottom-width: 1px;
        border-image-outset: 0;
        border-image-repeat: stretch;
        border-image-slice: 100%;
        border-image-source: none;
        border-image-width: 1;
        border-left-color: rgb(0, 0, 0);
        border-left-style: none;
        border-left-width: 0px;
        border-right-color: rgb(183, 197, 217);
        border-right-style: solid;
        border-right-width: 1px;
        border-top-color: rgb(0, 0, 0);
        border-top-style: none;
        border-top-width: 0px;
        color: rgb(0, 0, 0);
        display: table;
        font-family: arial, helvetica, sans-serif;
        font-size: 13.3333px;
        margin-bottom: 4px;
        margin-left: 0px;
        margin-right: 0px;
        margin-top: 4px;
        overflow-x: hidden;
        overflow-y: hidden;
        padding-bottom: 2px;
        padding-left: 2px;
        padding-right: 2px;
        padding-top: 2px;
    }

    .number {
        color: rgb(0, 0, 0);
        font-family: arial, helvetica, sans-serif;
        font-size: 13.3333px;
        width: 342.65px;
    }

    .op {
        color: rgb(0, 0, 0);
        font-family: arial, helvetica, sans-serif;
        font-size: 13.3333px;
        margin-bottom: 8px;
        margin-left: 0px;
        margin-right: 0px;
        margin-top: 4px;
        overflow-x: hidden;
        overflow-y: hidden;
    }

    .op blockquote {
        margin-left:7px;
    }

    .name {
        color: rgb(17, 119, 67);
        font-family: arial, helvetica, sans-serif;
        font-size: 13.3333px;
        font-weight: 700;
        margin-left: 7px;
    }

    .quote {
        color: rgb(221, 0, 0);
        font-family: arial, helvetica, sans-serif;
        font-size: 13.3333px;
        text-decoration-color: rgb(221, 0, 0);
        text-decoration-line: underline;
        text-decoration-style: solid;
        text-decoration-thickness: auto;
    }

    .greentext {
        color: rgb(120, 153, 34);
        font-family: arial, helvetica, sans-serif;
        font-size: 13.3333px;
    }

    blockquote {
        margin-block-start: 1em;
        margin-block-end: 1em;
        margin-inline-start: 40px;
        margin-inline-end: 40px;
    }
    """

    posts = []
    post = ''
    c = -2
    for line in f.splitlines():
        line += "\n"
        if line == '-----\n':
            continue
        elif line.startswith('--- '):
            c += 1
            if post != '':
                src = process_post(post, c)
                posts.append(src)
            post = line
        else:
            post += line
    if post != '':
        src = process_post(post, c)
        posts.append(src)

    for i in range(len(posts)):
        if i == 0:
            posts[i] = f'<div class="op">{posts[i]}</div>\n'
        else:
            posts[i] = f'<div class="reply">{posts[i]}</div>\n'
    
    output = ''
    output += f'<style>{css}</style><div id="container">'
    for post in posts:
        output += post
    output += '</div>'
    output = output.split('\n')
    for i in range(len(output)):
        output[i] = re.sub(r'^(&gt;(.*?)(<br>|</div>))', r'<span class="greentext">\1</span>', output[i])
        output[i] = re.sub(r'^<blockquote class="message">(&gt;(.*?)(<br>|</div>))', r'<blockquote class="message"><span class="greentext">\1</span>', output[i])
    output = '\n'.join(output)

    return output

def generate_chat_html(history, name1, name2):
    css = """
    .chat {
      margin-left: auto;
      margin-right: auto;
      max-width: 800px;
      height: 66.67vh;
      overflow-y: auto;
      padding-right: 20px;
      display: flex;
      flex-direction: column-reverse;
    }       

    .message {
      display: grid;
      grid-template-columns: 50px 1fr;
      padding-bottom: 20px;
      font-size: 15px;
      font-family: helvetica;
    }   
        
    .circle-you {
      width: 45px;
      height: 45px;
      background-color: rgb(244, 78, 59);
      border-radius: 50%;
    }
          
    .circle-bot {
      width: 45px;
      height: 45px;
      background-color: rgb(59, 78, 244);
      border-radius: 50%;
    }

    .circle-bot img {
      border-radius: 50%;
      width: 100%;
      height: 100%;
      object-fit: cover;
    }

    .text {
    }

    .text p {
      margin-top: 5px;
    }

    .username {
      font-weight: bold;
    }

    .body {
    }
    """

    output = ''
    output += f'<style>{css}</style><div class="chat" id="chat">'
    if Path("profile.png").exists():
        img = '<img src="file/profile.png">'
    elif Path("profile.jpg").exists():
        img = '<img src="file/profile.jpg">'
    elif Path("profile.jpeg").exists():
        img = '<img src="file/profile.jpeg">'
    else:
        img = ''

    for row in history[::-1]:
        row = list(row)
        row[0] = re.sub(r"[\\]*\*", r"*", row[0])
        row[1] = re.sub(r"[\\]*\*", r"*", row[1])
        row[0] = re.sub(r"(\*)([^\*]*)(\*)", r"<em>\2</em>", row[0])
        row[1] = re.sub(r"(\*)([^\*]*)(\*)", r"<em>\2</em>", row[1])
        p = '\n'.join([f"<p>{x}</p>" for x in row[1].split('\n')])
        output += f"""
              <div class="message">
                <div class="circle-bot">
                  {img}
                </div>
                <div class="text">
                  <div class="username">
                    {name2}
                  </div>
                  <div class="body">
                    {p}
                  </div>
                </div>
              </div>
            """

        p = '\n'.join([f"<p>{x}</p>" for x in row[0].split('\n')])
        output += f"""
              <div class="message">
                <div class="circle-you">
                </div>
                <div class="text">
                  <div class="username">
                    {name1}
                  </div>
                  <div class="body">
                    {p}
                  </div>
                </div>
              </div>
            """

    output += "</div>"
    return output
