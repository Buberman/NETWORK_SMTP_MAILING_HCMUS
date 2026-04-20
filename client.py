from distutils.command.check import check
import threading
import time
import queue
import socket
import os
import json
from email.mime.base import MIMEBase
from email import encoders
from email.parser import BytesParser
from email.policy import default
from email.header import decode_header
from email import policy
MAX_ATTACHMENT_SIZE_MB = 3

def wait_for_keypress():
    input("Nhấn phím bất kỳ để tiếp tục...")

def config_load(filename):
   with open(filename, 'r') as f:
       data = json.load(f)
   return data


def get_total_attachment_size(attachments):
    total_size = 0
    for attachment in attachments:
        if os.path.isfile(attachment):
            total_size += os.path.getsize(attachment)
    return total_size / (1024 * 1024)  # Convert to MB

def smtp_client(HOST,SMTP_PORT,CLIENT_DOMAIN,SENDER):
    
    smtp_client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    smtp_client_socket.connect((HOST,SMTP_PORT))
    smtp_client_socket.recv(1024)  # Receive initial server response

    smtp_client_socket.send(f'HELO {CLIENT_DOMAIN}\r\n'.encode())
    smtp_client_socket.recv(1024)  # Acknowledge HELO response

    print("Đây là thông tin soạn email: (nếu không điền vui lòng nhấn enter để bỏ qua)")
    RECEIVER = input('To: ')
    cc_recipients = input('CC: ')
    bcc_recipients = input('BCC: ')
    SUBJECT = input('Subject: ')
    MESSAGE = input('Content: ')

    attach_choice = input("Có gửi kèm file (1. có, 2. không): ")
    attachments = []
    if attach_choice == '1':
        num_attachments = int(input('Số lượng file muốn gửi: '))
        for i in range(num_attachments):
            attachment_path = input(f'Cho biết đường dẫn file thứ {i+1}: ')
            attachments.append(attachment_path)

    # Check attachment size
    if get_total_attachment_size(attachments) > MAX_ATTACHMENT_SIZE_MB:
        print(f"Attachments exceed the {MAX_ATTACHMENT_SIZE_MB} MB limit.")
        smtp_client_socket.close()
        return

    # Send MAIL FROM, RCPT TO commands
    smtp_client_socket.send(f'MAIL FROM: <{SENDER}>\r\n'.encode())
    smtp_client_socket.recv(1024)  # Acknowledge MAIL FROM response

    for recipient in [RECEIVER] + cc_recipients.split(',') + bcc_recipients.split(','):
        if recipient:
            smtp_client_socket.send(f'RCPT TO: <{recipient.strip()}>\r\n'.encode())
            smtp_client_socket.recv(1024)  # Acknowledge RCPT TO response

    # Send DATA command
    smtp_client_socket.send(b'DATA\r\n')
    smtp_client_socket.recv(1024)  # Acknowledge DATA command

    # Prepare and send email headers
    boundary = "my_attachment_boundary"
    email_headers = f"From: {SENDER}\r\nTo: {RECEIVER}\r\n"
    email_headers += f"Cc: {cc_recipients}\r\nSubject: {SUBJECT}\r\n"
    email_headers += "MIME-Version: 1.0\r\n"
    email_headers += f"Content-Type: multipart/mixed; boundary={boundary}\r\n\r\n"

    smtp_client_socket.send(email_headers.encode())

    # Email body part
    email_body = f"--{boundary}\r\nContent-Type: text/plain; charset=utf-8\r\n\r\n{MESSAGE}\r\n"
    smtp_client_socket.send(email_body.encode())

    # Attach files
    for attachment_path in attachments:
        if os.path.isfile(attachment_path):
            file_size = os.path.getsize(attachment_path)
            if file_size > 3 * 1024 * 1024:  # Size in bytes (3 MB)
                print(f"Attachment '{attachment_path}' is larger than 3 MB and will not be included.")
                continue  # Skip this file

            filename = os.path.basename(attachment_path)  # Extracts the filename from the file path
            with open(attachment_path, 'rb') as attachment_file:
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(attachment_file.read())
            encoders.encode_base64(part)
            part.add_header('Content-Disposition', f"attachment; filename= \"{filename}\"")  # Use the extracted filename

            smtp_client_socket.send(f"--{boundary}\r\n".encode() + part.as_string().encode() + b"\r\n")

    # End email
    smtp_client_socket.send(f"--{boundary}--\r\n".encode())
    smtp_client_socket.send(b'\r\n.\r\n')
    smtp_client_socket.recv(1024)  # Acknowledge end of DATA

    smtp_client_socket.send(b'QUIT\r\n')
    smtp_client_socket.recv(1024)  # Acknowledge QUIT command

    smtp_client_socket.close()
    print("Đã gửi email thành công")

# POP3 client function (unchanged)
def send_data(sock, data):
    try:
        sock.sendall(data.encode())
    except Exception as e:
        print(f"Error sending data: {e}")

def receive_data(sock):
    chunks = []
    while True:
        chunk = sock.recv(8192)
        if not chunk:
            break
        chunks.append(chunk)
        if b'\r\n' in chunk:
            # Check if the received data contains the termination sequence '\r\n'
            if chunks[-1].endswith(b'\r\n'):
                break
    return b''.join(chunks).decode()




def receive_mail_content(sock):
    content = b""
    while True:
        chunk = sock.recv(8192)
        if not chunk:
            break
        content += chunk
        if b'\r\n.\r\n' in content:
            break
    return content.decode()


def save_attachment(msg, download_path):
    attachments_saved = False
    for part in msg.walk():
        if part.get_content_maintype() == 'multipart':
            continue
        if part.get('Content-Disposition') is None:
            continue
        filename = part.get_filename()
        if filename:
            filepath = os.path.join(download_path, filename)
            with open(filepath, 'wb') as fp:
                fp.write(part.get_payload(decode=True))
            print(f"File saved as {filepath}")
            attachments_saved = True

    return attachments_saved

def get_sender(mail_content):
    # Remove lines starting with '+OK' (common in POP3)
    lines = mail_content.split('\n')
    lines = [line for line in lines if not line.startswith('+OK')]

    # Reconstruct the content without leading '+OK' lines
    cleaned_content = '\n'.join(lines)

    msg = BytesParser(policy=policy.default).parsebytes(cleaned_content.encode())

    # Try to get 'From' header
    sender = msg.get('From', '')

    # If 'From' header is not present, try to extract from other headers
    if not sender:
        sender = msg.get('X-Sender', '')
        if not sender:
            # If still not found, try to decode 'From' header
            sender_header = msg.get_all('From', [])
            sender, encoding = decode_header(sender_header[0] if sender_header else '')[0]

    return sender

def get_subject(mail_content):
    # Hàm này giúp lấy subject từ mail content
    lines = mail_content.split('\n')
    for line in lines:
        if line.startswith('Subject:'):
            return line[len('Subject:'):].strip()
    return ''

def remove_first_line(mail_content):
    # Split the content into lines
    lines = mail_content.splitlines()

    # Check if the first line starts with '+OK'
    if lines and lines[0].startswith('+OK'):
        # Exclude the first line and any empty lines
        lines = [line for line in lines[1:] if line]

    new_content = '\n'.join(lines)

    return new_content


def categorize_mail(subject, category_keywords):
    # Hàm này kiểm tra subject và trả về category tương ứng
    if category_keywords:
        for category, keywords in category_keywords.items():
            if any(keyword.lower() in subject.lower() for keyword in keywords):
                return category
    # Nếu không khớp với bất kỳ category nào, trả về 'inbox' làm mặc định
    return 'Inbox'

def categorize_mail_by_content(mail_content, keyword_mapping):

    for keyword, category in keyword_mapping.items():
        if keyword.lower() in mail_content.lower():
            return keyword
    return 'Inbox'

def clear_mailbox(mailbox_path):
    # Remove all files in the specified directory
    for root, dirs, files in os.walk(mailbox_path):
        for file in files:
            file_path = os.path.join(root, file)
            os.remove(file_path)

def create_category_folder(mailbox_path, category):
    # Ensure the category folder exists, create if not
    category_folder = os.path.join(mailbox_path, category)
    os.makedirs(category_folder, exist_ok=True)

def join_path(path, folder):  
    combined = f"{path}\\{folder}"
    return combined

def create_directory(directory_path):
    if not os.path.exists(directory_path):
        os.makedirs(directory_path)

def save_email_content(filepath, mail_content):
    # Check if the file already exists
    if os.path.exists(filepath):
        # If the file exists, truncate it (clear content)
        with open(filepath, 'wb') as file:
            file.truncate()
    else:
        # If the file doesn't exist, create it
        os.makedirs(os.path.dirname(filepath), exist_ok=True)

    # Write the new email content to the file
    with open(filepath, 'ab') as file:
        file.write(mail_content.encode())



def parse_email_content(raw_content):
    msg = BytesParser(policy=policy.default).parsebytes(raw_content.encode())
    for part in msg.walk():
        if part.get_content_type() == 'text/plain':
            return part.get_payload(decode=True).decode()
    return ""


def is_sender_in_project_list(sender, project_sender_list):
    return sender in project_sender_list

def download_mail(host, port, username, password, mailbox_path, category_keywords=None, project_sender_list=None):

    with socket.create_connection((host, port)) as client_socket:
            
            receive_data(client_socket)  # Nhận phản hồi kết nối đầu tiên

            send_data(client_socket, f'USER {username}\r\n')
            receive_data(client_socket)

            # Gửi lệnh PASS và nhận phản hồi
            send_data(client_socket, f'PASS {password}\r\n')
            receive_data(client_socket)

            # Gửi lệnh LIST và nhận phản hồi
            send_data(client_socket, 'LIST\r\n')
            response = receive_data(client_socket)

            # Lấy danh sách số thứ tự của thư
            mail_ids = [line.split()[0] for line in response.splitlines()[1:]]

            # Lặp qua từng thư và lưu vào mailbox (lọc dựa trên subject nếu có)
            for mail_id in mail_ids:
                if(mail_id=='.'): break
                send_data(client_socket, f'RETR {mail_id}\r\n')
                mail_content = receive_mail_content(client_socket)
                
                content = parse_email_content(mail_content)
                # Sử dụng hàm get_subject để lấy subject từ mail content
                subject = get_subject(content)

                # Kiểm tra subject và phân loại vào các categories
                matching_category_subject = categorize_mail(subject, category_keywords)
                matching_category_content = categorize_mail_by_content(mail_content, category_keywords)

                # Lấy sender từ content
                sender = get_sender(mail_content)
    
                # Kiểm tra nếu sender nằm trong danh sách 'Project'
                if is_sender_in_project_list(sender, project_sender_list):
                    project_filepath = os.path.join(mailbox_path, 'Project', f"{mail_id}.eml")
                    if not os.path.exists(project_filepath):
                        save_email_content(project_filepath, content)

                # Tạo đường dẫn cho mỗi thư trong mailbox
                mail_filename = f"{mail_id}.eml"
                inbox_filepath = os.path.join(mailbox_path, 'Inbox', mail_filename)
                category_filepath_subject = os.path.join(mailbox_path, matching_category_subject, mail_filename)
                category_filepath_content = os.path.join(mailbox_path, matching_category_content, mail_filename)
                # Lưu nội dung thư vào tập tin trong 'inbox'
                if not os.path.exists(inbox_filepath):
                    save_email_content(inbox_filepath, content)

                
                if matching_category_subject != 'Inbox':
                    if not os.path.exists(category_filepath_subject):
                        save_email_content(category_filepath_subject, content)     
                if matching_category_content != 'Inbox' and matching_category_subject == 'Inbox':
                    if not os.path.exists(category_filepath_content):
                        save_email_content(category_filepath_content, content)
    
       
            
    
    
    
        



def list_folders(mailbox_path):
    folders = os.listdir(mailbox_path)
    print("Đây là danh sách các folder trong mailbox của bạn:")
    for idx, folder in enumerate(folders, 1):
        print(f"{idx}. {folder}")
    return folders

def parse_eml_file(file_path):
    with open(file_path, 'rb') as file:
        eml_content = file.read()

    return parse_eml_content(eml_content)

def parse_eml_content(eml_content):
    # Remove lines starting with '+OK' (common in POP3)
    lines = eml_content.decode('utf-8').split('\n')
    lines = [line for line in lines if not line.startswith('+OK')]

    # Reconstruct the content without leading '+OK' lines
    cleaned_content = '\n'.join(lines)

    msg = BytesParser(policy=policy.default).parsebytes(cleaned_content.encode())

    # Try to get 'Subject' header
    subject = msg.get('Subject', '')

    # Try to get 'From' header
    sender = msg.get('From', '')

    # If 'From' header is not present, try to extract from other headers
    if not sender:
        sender = msg.get('X-Sender', '')
        if not sender:
            # If still not found, try to decode 'From' header
            sender_header = msg.get_all('From', [])
            sender, encoding = decode_header(sender_header[0] if sender_header else '')[0]

    to = msg.get_all('To', [])
    to_addresses = [addr[0] for addr in decode_header(to[0])] if to else []

    # Lấy danh sách các địa chỉ email trong trường 'Cc'
    cc = msg.get_all('Cc', [])
    cc_addresses = [addr[0] for addr in decode_header(cc[0])] if cc else []

    # Lấy danh sách các địa chỉ email trong trường 'Bcc'
    bcc = msg.get_all('Bcc', [])
    bcc_addresses = [addr[0] for addr in decode_header(bcc[0])] if bcc else []

    # Lấy nội dung của email
    content = ""
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            if content_type == "text/plain":
                content = part.get_payload(decode=True).decode()
                break
    else:
        content = msg.get_payload(decode=True).decode()

    attachments = []
    if msg.is_multipart():
        for part in msg.walk():
            content_disposition = part.get("Content-Disposition", None)
            if content_disposition and "attachment" in content_disposition:
                filename = part.get_filename()
                if filename:
                    attachments.append((filename, part.get_payload(decode=True)))
    return sender, subject, to_addresses, cc_addresses, bcc_addresses, content, attachments

def list_emails_in_folder(mailbox_path, folder_name):
    folder_path = os.path.join(mailbox_path, folder_name)
    if not os.path.exists(folder_path):
        print(f"Folder '{folder_name}' does not exist.")
        return []

    all_mails = [f for f in os.listdir(folder_path) if os.path.isfile(os.path.join(folder_path, f)) and f.endswith('.eml')]
    # Sắp xếp thư theo tên tập tin (giả sử tên tập tin là số ID thư)
    all_mails.sort(key=lambda x: int(x.split('.')[0]))

    print(f"\nĐây là danh sách email trong {folder_name} folder:")
    for idx, mail in enumerate(all_mails, 1):
        mail_path = os.path.join(folder_path, mail)
        sender, subject, to_addresses, cc_addresses, bcc_addresses, content, attachments = parse_eml_file(mail_path)
        print(f"{idx}. {sender} - {subject}")
    return all_mails



def read_mail(mailbox_path):
   
    os.system('cls')
    folders = list_folders(mailbox_path)
    folder_index = input("Bạn muốn xem email trong folder nào: ")
    if not folder_index:
            print("Thoát ra ngoài.")
            return

    try:
        folder_index = int(folder_index)
    except ValueError:
            print("Lựa chọn folder không hợp lệ.")
            return
    
    if folder_index < 1 or folder_index > len(folders):
            print("Lựa chọn folder không hợp lệ.")
            return
    while True:
        

        selected_folder = folders[folder_index - 1]
        all_mails = list_emails_in_folder(mailbox_path, selected_folder)
        if not all_mails:
           print("Không có email nào trong thư mục này.")
           return
        mail_choice = input("\nBạn muốn đọc Email thứ mấy? (hoặc nhấn enter để thoát ra ngoài, hoặc nhấn 0 để xem lại danh sách email): ")

        if mail_choice == '':
            print("Thoát khỏi chức năng đọc email.")
            break
        elif mail_choice == '0':
            continue
        else:
            try:
                mail_index = int(mail_choice)
                if 1 <= mail_index <= len(all_mails):
                    mail_filename = all_mails[mail_index - 1]
                    mail_filepath = os.path.join(mailbox_path, selected_folder, mail_filename)
                    with open(mail_filepath, 'rb') as eml_file:
                        eml_content = eml_file.read()

                    # Phân tích nội dung email và hiển thị thông tin
                    sender, subject, to_addresses, cc_addresses, bcc_addresses, content, attachments = parse_eml_content(eml_content)
                    print("\nThông tin email:")
                    print("-------------------------------------------")
                    print(f"Người gửi: {sender}")
                    print(f"Chủ đề: {subject}")
                    print(f"Đến: {', '.join(to_addresses)}")
                    print(f"Cc: {', '.join(cc_addresses)}")
                    print(f"Bcc: {', '.join(bcc_addresses)}")
                    print("Nội dung email:")
                    print(content)
                    print("-------------------------------------------")
                    if attachments:
                        print("File đính kèm:")
                        for attachment in attachments:
                            print(attachment[0])
                        download_choice = input("Bạn có muốn tải các file đính kèm này không? (y/n): ")
                        if download_choice.lower() == 'y':
                            download_path = input("Nhập đường dẫn để lưu các file đính kèm: ")
                            for attachment in attachments:
                                filepath = os.path.join(download_path, attachment[0])
                                with open(filepath, 'wb') as file:
                                    file.write(attachment[1])
                                print(f"Đã tải '{attachment[0]}' vào {filepath}")
                    wait_for_keypress()
                else:
                    print("Số thứ tự email không hợp lệ.")
                    wait_for_keypress()

            except ValueError:
                print("Lựa chọn không hợp lệ. Vui lòng nhập số.")
                wait_for_keypress()
                

def auto_load(host, port, username, password, mailbox_path, autoload_timer, category_keywords=None, project_sender_list=None):
    
    create_category_folder(mailbox_path, 'Inbox')
    if category_keywords:
        for category in category_keywords.keys():
            create_category_folder(mailbox_path, category)

    # Ensure the 'Project' folder exists
    create_category_folder(mailbox_path, 'Project')
    
    while True:
        download_mail(host, port, username, password, mailbox_path, category_keywords, project_sender_list)
        time.sleep(int(float(autoload_timer)))

def main_menu(HOST,SMTP,POP3,CLIENT_DOMAIN,SENDER,USERNAME,PASSWORD, MAILBOX_PATH):

    while True:
        os.system('cls')
        
        print("Vui lòng chọn Menu:")
        print("1. Để gửi email")
        print("2. Để xem danh sách các email đã nhận")
        print("3. Thoát")
        choice = input("Bạn chọn: ")

        if choice == '1':
            os.system('cls')
            smtp_client(HOST,SMTP,CLIENT_DOMAIN,SENDER)
        elif choice == '2':
            os.system('cls')
            read_mail(MAILBOX_PATH)
        elif choice == '3':
            
            print('Bye!')
            break
        else:
            print("Lựa chọn không hợp lệ. Vui lòng thử lại.")

if __name__ == "__main__":
    category_keywords = {
        'Inbox': ['general', 'regular'],
        'Important': ['important', 'urgent'],
        'Spam': ['promotion', 'advertisement', 'spam'],
        'Work': ['project', 'deadline', 'meeting']
    }
    sender_keyword = ['khoa_tv@gmail.com', 'project.team@example.com', 'important.sender@example.com']
    data = config_load("config.json")
    mailbox_path = join_path('C:\\data',data['USERNAME'])
    autoload_thread = threading.Thread(target=auto_load, args=(data['HOST'],data['POP3_PORT'],data["USERNAME"], data['PASSWORD'],mailbox_path,data['AUTOLOAD'], category_keywords,sender_keyword,))
    try:
        autoload_thread.start()
        main_menu(data['HOST'],int(data['SMTP_PORT']),int(data['POP3_PORT']),data['CLIENT_DOMAIN'],data['SENDER'],data["USERNAME"], data['PASSWORD'],mailbox_path)
    except KeyboardInterrupt:
        pass
    finally:
        autoload_thread.join()
    