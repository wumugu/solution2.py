import zipfile
import re

ARCHIVE = "twc12_http_archive.zip"


z = zipfile.ZipFile(ARCHIVE)
files = [name for name in z.namelist() if name.endswith(".bin")]


def parse(block):
    head, _, tail = block.partition(b"\r\n\r\n")
    lines = head.split(b"\r\n")

    headers = {}
    for line in lines[1:]:
        name, value = line.split(b":", 1)
        headers.setdefault(name.lower(), []).append(value.strip())

    if b"content-length" in headers:
        body = tail[:int(headers[b"content-length"][0])]
    else:
        body = tail[:-2]  # final \n\n added by the logger

    return lines[0], headers, body


def pairs(data):
    parts = re.split(rb"===== (REQUEST|RESPONSE) =====\n", data)

    for i in range(1, len(parts) - 3, 4):
        request = parse(parts[i + 1])
        response = parse(parts[i + 3])
        yield request, response


def check(data):
    store = {}

    for request, response in pairs(data):
        req_line, req_headers, req_body = request
        res_line, res_headers, res_body = response

        method, url, _ = req_line.split(b" ")
        key = url[1:]
        code = res_line.split(b" ")[1]

        if method == b"GET":
            if key in store:
                if code != b"200" or res_body != store[key]:
                    return False
            elif code != b"404":
                return False

        elif method == b"POST":
            if code != b"202":
                return False
            if res_body != req_body:
                return False
            if res_headers.get(b"x-length") != [str(len(req_body)).encode()]:
                return False

            store[key] = req_body

        elif method == b"DELETE":
            if key in store:
                checksum = 0
                for byte in store[key]:
                    checksum ^= byte

                if code != b"204":
                    return False
                if res_body != b"":
                    return False
                if res_headers.get(b"x-checksum") != [str(checksum).encode()]:
                    return False

                del store[key]
            elif code != b"404":
                return False

        elif method == b"SHOW":
            thing = req_headers.get(b"thing")

            if code != b"218":
                return False

            # If Thing is absent, the protocol does not define the response.
            if thing is not None:
                expected = b"That is nice " + thing[0] + b"."
                if res_body != expected:
                    return False

        # Other valid HTTP methods are not described by the storage protocol.

    return True


good = 0

for name in files:
    if check(z.read(name)):
        good += 1

print(f"{good / len(files) * 100:.2f}")
