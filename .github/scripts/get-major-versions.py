import argparse
import json
import os
import re
import sys
import requests
import time
from datetime import datetime, timezone
import shutil, errno, stat
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from dotenv import load_dotenv

load_dotenv()

DOCKERHUB_USERNAME=os.getenv('DOCKERHUB_USERNAME')
DOCKERHUB_TOKEN=os.getenv('DOCKERHUB_TOKEN')

os_variants_map = {
    "20348": "ltsc2022",    # winamd64
    "17763": "1809",        # winamd64
    "17134": "1803",        # winamd64
    "16299": "1709",        # winamd64
    "14393": "ltsc2016"     # winamd64
}
    

def create_session(image_name, namespace):
    session = requests.Session()
    retry_strategy = Retry(
        total=3,  # Retry up to 3 times
        backoff_factor=1,  # Wait 1, 2, 4 seconds between retries
        status_forcelist=[403, 429, 500, 502, 503, 504],
        allowed_methods=["GET"]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)

    return session

def create_dockerhub_authenticated_session(image_name, namespace):
    session = create_session(image_name, namespace)
    # Generate token Docker Hub Access Token
    # Docs: https://docs.docker.com/reference/api/hub/latest/#tag/authentication-api/operation/AuthCreateAccessToken
    response = session.post(f"https://hub.docker.com/v2/auth/token", json={'identifier': DOCKERHUB_USERNAME, 'secret': DOCKERHUB_TOKEN})
    token = response.json().get('access_token')
    session.headers.update({
        'Authorization': f'Bearer {token}',
        'Accept': 'application/json'
    })
    return session

def check_last_updated_tag(result_tag, last_updated=None):
    if last_updated is None:
        return None
    last_updated_ts = datetime.fromisoformat(last_updated).timestamp()
    if result_tag and 'last_updated' in result_tag:
        result_last_updated_ts = datetime.fromisoformat(result_tag.get('last_updated')).timestamp()
        return result_last_updated_ts < last_updated_ts
    return None

def check_last_updated_paged_results(result_tags, last_updated=None):
    if last_updated is None:
        return False
    for result in result_tags:
        if check_last_updated_tag(result, last_updated):
            return True
    return False

def get_tags(image_name, namespace, last_updated=None, page_size=100):
    url = f"https://registry.hub.docker.com/v2/namespaces/{namespace}/repositories/{image_name}/tags?page_size={page_size}"
    all_tags = []
    start=int(time.time() * 1000)
    print(f"Fetching tags from Docker API for {namespace}/{image_name}...")
    session = create_dockerhub_authenticated_session(image_name, namespace)
    while url:
        time.sleep(0.5)  # Sleep for 500 milliseconds to avoid rate limiting
        response = session.get(url)
        print(f'GET {url} - {response.elapsed.microseconds // 1000} ms')
        if response.status_code == 200:
            tags_data = response.json()
            if last_updated and check_last_updated_paged_results(tags_data['results'], last_updated):
                print("Last checked tag found, stopping further requests.")
                all_tags.extend([tag for tag in tags_data['results'] if not check_last_updated_tag(tag, last_updated)])
                break
            else:
                all_tags.extend(tags_data['results'])
            url = tags_data.get('next')
        else:
            exit(f"Failed to fetch tags from Docker Hub. Status Code: {response.status_code}, Response: {response.text}")   
    duration=int(time.time() * 1000) - start
    print(f"Successfully fetched tags - {duration} ms")
    return all_tags

def get_major_version_from_tags(tags):
    match = match_version_from_tags(tags, '^\\d+\\.\\d+-\\w+$')
    if match:
        version = match.split('-')
        return version[0], version[1]
    return None, None

def match_version_from_tags(tags, pattern):
    for tag in tags:
        match = re.search(pattern, tag)
        if match:
            return match.group(0)
    return None

def get_digest_versions(image_name, namespace, last_updated=None):
    tags = get_tags(image_name, namespace, last_updated=last_updated, page_size=10 if last_updated else 100)
    if tags:
        print(f"found {len(tags)} tags")
        digest_versions = {}
        for tag_info in tags:
            tag = tag_info['name']
            version = tag.split('.')[0].split('-')[0]  # Extracting the major version
            # exclude major version earlier than min_major_version and later than max_major_version
            if  not ( version.isdigit() and (int(version) < min_major_version or int(version) > max_major_version)):
                print(f"found tag: {tag}")
                for img in tag_info['images']:
                    digest, os, arch = get_image_os_arch(img)
                    if os and arch and digest:
                        if digest not in digest_versions:
                            digest_versions[digest] = {'OS/Arch': f"{os}/{arch}", 'Tags': [], 'codenames': None}
                        digest_versions[digest]['Tags'].append(tag)
                        if digest_versions[digest]['codenames'] is None and len(tag.split('-')) > 1:
                            digest_versions[digest]['codenames'] = tag.split('-')[1]                
        # Filter out major versions with only single-digit tags
        digest_versions = {digest: info for digest, info in digest_versions.items() if match_version_from_tags(info['Tags'], '^\\d+\\.\\d+$') and info.get('codenames') is not None and info.get('codenames') not in exclude_codenames}
        return digest_versions
    else:
        print("No tags found or failed to fetch tags.")
        return None
    
def get_latest_last_updated(current_major_versions):
    if current_major_versions is None:
        return None
    latest_last_updated = None
    for major_version in current_major_versions.values():
        for os_version in major_version.values():
            last_updated = os_version.get('last_updated')
            if not last_updated:
                return None  # If any last_updated is missing, return None
            if latest_last_updated is None or last_updated > latest_last_updated:
                latest_last_updated = last_updated
    return latest_last_updated
    
    
def get_major_versions(image_name, namespace, current_major_versions=None):
    last_updated = get_latest_last_updated(current_major_versions)
    # get the current UTC iso format timestamp
    now = datetime.now(timezone.utc).isoformat()
    digest_versions = get_digest_versions(image_name, namespace, last_updated=last_updated)
    major_versions = {} if current_major_versions is None or last_updated is None else current_major_versions
    
    if digest_versions is not None:
        # Update major_versions with new digest information
        for digest in digest_versions.keys():
            digest_info = digest_versions[digest]
            m_version, os_version = get_major_version_from_tags(digest_info["Tags"])
            if m_version not in major_versions:
                major_versions[m_version] = {}
            ordered_tags=sorted(digest_info["Tags"], key=lambda x: (-len(x), x))
            if os_version not in major_versions[m_version]:
                major_versions[m_version][os_version] = {'name': match_version_from_tags(ordered_tags, '^\\d+(\\.\\d+){0,2}-\\w+$'), 'tags': ordered_tags, 'platforms': [], 'meta': {'images': []}}
            major_versions[m_version][os_version]["platforms"].append(digest_info["OS/Arch"])
            major_versions[m_version][os_version]["meta"]["images"].append({'digest': digest, 'platform': digest_info["OS/Arch"]})
            major_versions[m_version][os_version]["platforms"] = sorted(major_versions[m_version][os_version]["platforms"], key=str)
            major_versions[m_version][os_version]["meta"]["images"] = sorted(major_versions[m_version][os_version]["meta"]["images"], key = lambda image: (isinstance(image["platform"], str), image["platform"]))
            major_versions[m_version][os_version]["last_updated"] = now
            
    return major_versions

def get_image_os_arch(image):
    os = image.get('os')
    arch = image.get('architecture')
    digest = image.get('digest')
    os_var = image.get('os_version')
    print(f"checking tag info: os={os}, os_variant={os_var}, arch={arch}, digest={digest}")
    # filter out os/arch
    if (disable_linux_fetching and os == "linux") or (disable_windows_fetching and os == "windows"):
        print("OS not allowed!")
        return None, None, None
    if (exclude_arch and arch in exclude_arch) or (allowed_arch and len(allowed_arch) > 0 and arch not in allowed_arch):
        print("Arch not allowed!")
        return None, None, None
    if len(os.strip()) == 0 or os == "unknown" or len(arch.strip()) == 0 or arch == 'unknown':
        print("Unknown OS/Arch not allowed!")
        return None, None, None
    
    if os_var:
        variant = os_variants_map.get(os_var.split('.')[2])
        return digest, f"{os}-{variant}", arch
    else:
        return digest, os, arch
    
def load_current_major_versions():
    if os.path.exists('build_info'):
        major_versions = {}
        for version_dir in os.listdir('build_info'):
            version_path = os.path.join('build_info', version_dir)
            if os.path.isdir(version_path):
                version_parts = version_dir.split('.')
                major_version = ".".join([version_parts[0], version_parts[1]])
                major_versions[major_version] = {}
                for os_version_dir in os.listdir(version_path):
                    os_version_path = os.path.join(version_path, os_version_dir)
                    if os.path.isdir(os_version_path):
                        build_info_file = os.path.join(os_version_path, 'build_info.json')
                        if os.path.exists(build_info_file):
                            with open(build_info_file, 'r') as f:
                                major_versions[major_version][os_version_dir] = json.load(f)
        return major_versions
    return None

def main(image_name, namespace):
    current_major_versions = load_current_major_versions()
    major_versions = get_major_versions(image_name, namespace, current_major_versions)
    if major_versions:
        print("Saving major versions to build_info directory...")
        for version in major_versions.keys():
            for os_version in major_versions[version].keys():
                output_file = f'build_info/{version}.0/{os_version}/build_info.json'
                os.makedirs(os.path.dirname(output_file), exist_ok=True)
                print(f"Saving build info for version {version}.0 and OS {os_version} to {output_file}")
                with open(output_file, 'w') as f:
                    json.dump(major_versions[version][os_version], f, indent=4)
    else:
        raise ValueError("Failed to get major versions.") 

def handle_remove_readonly(func, path, exc):
  excvalue = exc[1]
  if func in (os.rmdir, os.remove) and excvalue.errno == errno.EACCES:
      os.chmod(path, stat.S_IRWXU| stat.S_IRWXG| stat.S_IRWXO) # 0777
      try:
          func(path)
      except Exception:
          pass
  else:
      raise

def del_current_build_info():
    path = os.path.abspath('build_info')
    if os.path.isdir(path):
        shutil.rmtree(path, ignore_errors=False, onerror=handle_remove_readonly)
        
disable_linux_fetching:bool = None
disable_windows_fetching:bool = None
min_major_version: int = None
max_major_version: int = None
allowed_arch:list = None
exclude_arch:list = None
exclude_codenames:list = None

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('-n', '--namespace', type=str, default='library')
    parser.add_argument('-i', '--image_name', type=str, required=True)
    parser.add_argument('--disable_linux',  action='store_true', default=False)
    parser.add_argument('--disable_windows',  action='store_true', default=False)
    parser.add_argument('--min_major', type=int, default=0)
    parser.add_argument('--max_major', type=int, default=sys.maxsize)
    parser.add_argument('--allowed_arch', nargs="+", action="extend", type=str, default=[])
    parser.add_argument('--exclude_arch', nargs="+", action="extend", type=str, default=[])
    parser.add_argument('--exclude_codenames', nargs="+", action="extend", type=str, default=[])
    args = parser.parse_args()
    
    namespace = args.namespace
    image_name = args.image_name
    disable_linux_fetching = args.disable_linux
    disable_windows_fetching = args.disable_windows
    min_major_version = args.min_major
    max_major_version = args.max_major
    allowed_arch = args.allowed_arch
    exclude_arch = args.exclude_arch
    exclude_codenames = args.exclude_codenames or []
    
    print(f"disable_linux_fetching={disable_linux_fetching}")
    print(f"disable_windows_fetching={disable_windows_fetching}")
    print(f"min_major_version={min_major_version}")
    print(f"max_major_version={max_major_version}")
    print(f"allowed_arch={allowed_arch}")
    print(f"exclude_arch={exclude_arch}")
    print(f"exclude_codenames={exclude_codenames}")
    
    if any(i in allowed_arch for i in exclude_arch):
        raise Exception("allowed_arch and exclude_arch can not contain any matching!")
    
    # del_current_build_info()
    main(image_name, namespace)