import os
import time
import logging
import requests
from urllib.parse import urlparse, urljoin, unquote
from bs4 import BeautifulSoup
import re
import shutil
from urllib.request import Request, urlopen

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class WebsiteScraper:
    def __init__(self, base_url, output_dir, max_depth=1, download_assets=True):
        self.base_url = base_url
        self.output_dir = output_dir
        self.max_depth = max_depth
        self.download_assets = download_assets
        self.visited_urls = set()
        self.to_visit = [(base_url, 0)]  # (url, depth)
        self.progress = 0
        self.files_downloaded = 0
        self.total_size = 0  # in bytes
        self.errors = []
        
        # Parse and save the domain for later use
        parsed_url = urlparse(base_url)
        self.domain = parsed_url.netloc
        self.scheme = parsed_url.scheme
        
        # Create the base directory
        os.makedirs(output_dir, exist_ok=True)
    
    def start_scraping(self):
        """Start the scraping process"""
        try:
            while self.to_visit:
                url, depth = self.to_visit.pop(0)
                
                if url in self.visited_urls:
                    continue
                
                self.visited_urls.add(url)
                logger.info(f"Processing URL: {url} at depth {depth}")
                
                try:
                    self.process_url(url, depth)
                except Exception as e:
                    logger.error(f"Error processing URL {url}: {e}")
                    self.errors.append(f"Failed to process {url}: {str(e)}")
                
                # Update progress
                self.progress = len(self.visited_urls) / (len(self.visited_urls) + len(self.to_visit)) * 100
                time.sleep(0.1)  # Small delay to avoid overwhelming the server
                
            logger.info("Scraping completed!")
        except Exception as e:
            logger.error(f"Error in scraping process: {e}")
            self.errors.append(f"Scraping error: {str(e)}")
    
    def process_url(self, url, depth):
        """Process a URL: download the page and parse for links"""
        # Skip URLs that are not on the same domain
        if urlparse(url).netloc != self.domain:
            return
        
        # Skip URL fragments and query parameters for now
        url = self._clean_url(url)
        
        try:
            # Make the request
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
            }
            response = requests.get(url, headers=headers, timeout=10)
            
            # Determine the file path for saving
            file_path = self._get_file_path(url)
            
            # Create directories if they don't exist
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            if response.status_code != 200:
                # Create an error page for missing content
                self.errors.append(f"Failed to fetch {url}: HTTP {response.status_code}")
                
                # Create a placeholder HTML page with error information
                html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Error - {url}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; line-height: 1.6; }}
        .error-container {{ background-color: #f8d7da; border: 1px solid #f5c6cb; padding: 20px; border-radius: 5px; }}
        h1 {{ color: #721c24; }}
        .url {{ word-break: break-all; background-color: #f8f9fa; padding: 10px; border-radius: 5px; }}
    </style>
</head>
<body>
    <div class="error-container">
        <h1>Error Accessing Page</h1>
        <p>The requested URL could not be accessed during the website archiving process.</p>
        <p><strong>URL:</strong> <span class="url">{url}</span></p>
        <p><strong>Status Code:</strong> {response.status_code}</p>
        <p><strong>Original Path:</strong> {urlparse(url).path}</p>
        <p>This placeholder page was created by WebArchiver.</p>
    </div>
</body>
</html>"""
                # Save the error page
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(html_content)
                
                self.files_downloaded += 1
                self.total_size += len(html_content)
                return
            
            # If this is an HTML page, parse it and extract links
            content_type = response.headers.get('Content-Type', '').lower()
            
            if 'text/html' in content_type:
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Update links in the HTML to point to local files
                self._update_html_links(soup, url)
                
                # Find all links and add them to the queue if we're not at max depth
                if depth < self.max_depth:
                    self._extract_links(soup, url, depth)
                
                # If we're downloading assets, process them
                if self.download_assets:
                    self._extract_and_download_assets(soup, url)
                
                # Save the modified HTML
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(str(soup))
            else:
                # For non-HTML content, just save the file
                with open(file_path, 'wb') as f:
                    f.write(response.content)
            
            self.files_downloaded += 1
            self.total_size += len(response.content)
            
        except Exception as e:
            logger.error(f"Error processing {url}: {e}")
            self.errors.append(f"Error processing {url}: {str(e)}")
            
            # Create an error page for exceptions
            try:
                # Get the file path for this URL
                error_file_path = self._get_file_path(url)
                
                # Ensure the directory exists
                os.makedirs(os.path.dirname(error_file_path), exist_ok=True)
                
                html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Error - {url}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; line-height: 1.6; }}
        .error-container {{ background-color: #f8d7da; border: 1px solid #f5c6cb; padding: 20px; border-radius: 5px; }}
        h1 {{ color: #721c24; }}
        .url {{ word-break: break-all; background-color: #f8f9fa; padding: 10px; border-radius: 5px; }}
    </style>
</head>
<body>
    <div class="error-container">
        <h1>Error Processing Page</h1>
        <p>An error occurred while trying to process this page during the website archiving process.</p>
        <p><strong>URL:</strong> <span class="url">{url}</span></p>
        <p><strong>Error:</strong> {str(e)}</p>
        <p>This placeholder page was created by WebArchiver.</p>
    </div>
</body>
</html>"""
                
                # Save the error page
                with open(error_file_path, 'w', encoding='utf-8') as f:
                    f.write(html_content)
                
                self.files_downloaded += 1
                self.total_size += len(html_content)
            except Exception as inner_e:
                logger.error(f"Error creating error page for {url}: {inner_e}")
    
    def _clean_url(self, url):
        """Remove fragments and standardize URL, with Webflow-specific handling"""
        parsed = urlparse(url)
        path = parsed.path
        
        # Special case for webflow sites where URL structure doesn't use /index.html
        if 'webflow.io' in parsed.netloc:
            # Handle specific URL pattern conversion: /home-v2/index.html -> /home-pages/home-v2
            if '/home-v2/index.html' in path:
                path = path.replace('/home-v2/index.html', '/home-pages/home-v2')
            elif '/home-v3/index.html' in path:
                path = path.replace('/home-v3/index.html', '/home-pages/home-v3')
            elif '/blog-v1/index.html' in path:
                path = path.replace('/blog-v1/index.html', '/blog-pages/blog-v1')
            elif '/blog-v2/index.html' in path:
                path = path.replace('/blog-v2/index.html', '/blog-pages/blog-v2')
            elif '/blog-v3/index.html' in path:
                path = path.replace('/blog-v3/index.html', '/blog-pages/blog-v3')
            elif '/contact-v1/index.html' in path:
                path = path.replace('/contact-v1/index.html', '/contact-pages/contact-v1')
            elif '/contact-v2/index.html' in path:
                path = path.replace('/contact-v2/index.html', '/contact-pages/contact-v2')
            elif '/contact-v3/index.html' in path:
                path = path.replace('/contact-v3/index.html', '/contact-pages/contact-v3')
            # General pattern for removing /index.html from paths for webflow sites
            elif path.endswith('/index.html'):
                path = path[:-11]  # Remove /index.html
                
        return f"{parsed.scheme}://{parsed.netloc}{path}"
    
    def _get_file_path(self, url):
        """Convert a URL to a local file path"""
        parsed = urlparse(url)
        path = parsed.path.strip('/')
        
        # Default to index.html for empty paths
        if not path:
            path = 'index.html'
        # Add .html extension if there's no extension
        elif '.' not in os.path.basename(path):
            path = os.path.join(path, 'index.html')
        
        # Decode URL-encoded characters
        path = unquote(path)
        
        return os.path.join(self.output_dir, path)
    
    def _update_html_links(self, soup, current_url):
        """Update links in HTML to point to local files"""
        # Update anchor links
        for a_tag in soup.find_all('a', href=True):
            href = a_tag['href']
            if not href.startswith('#') and not href.startswith('javascript:'):
                absolute_url = urljoin(current_url, href)
                if urlparse(absolute_url).netloc == self.domain:
                    relative_path = self._get_relative_path(current_url, absolute_url)
                    a_tag['href'] = relative_path
                    # Add data attribute to track 404 links
                    a_tag['data-original-url'] = absolute_url
        
        # Update stylesheets
        for link_tag in soup.find_all('link', rel='stylesheet', href=True):
            href = link_tag['href']
            absolute_url = urljoin(current_url, href)
            relative_path = self._get_relative_path(current_url, absolute_url)
            link_tag['href'] = relative_path
            link_tag['data-original-url'] = absolute_url
        
        # Update scripts
        for script_tag in soup.find_all('script', src=True):
            src = script_tag['src']
            absolute_url = urljoin(current_url, src)
            relative_path = self._get_relative_path(current_url, absolute_url)
            script_tag['src'] = relative_path
            script_tag['data-original-url'] = absolute_url
        
        # Update images
        for img_tag in soup.find_all('img', src=True):
            src = img_tag['src']
            absolute_url = urljoin(current_url, src)
            relative_path = self._get_relative_path(current_url, absolute_url)
            img_tag['src'] = relative_path
            img_tag['data-original-url'] = absolute_url
    
    def _get_relative_path(self, from_url, to_url):
        """Calculate the relative path from one URL to another"""
        from_parsed = urlparse(from_url)
        to_parsed = urlparse(to_url)
        
        # If different domains, keep the absolute URL
        if from_parsed.netloc != to_parsed.netloc:
            return to_url
        
        # Get the file paths
        from_path = from_parsed.path.strip('/')
        to_path = to_parsed.path.strip('/')
        
        # If from_path is empty, it's the root
        if not from_path:
            from_path = 'index.html'
        # Add index.html for directory paths
        elif '.' not in os.path.basename(from_path):
            from_path = os.path.join(from_path, 'index.html')
        
        # Same for to_path
        if not to_path:
            to_path = 'index.html'
        elif '.' not in os.path.basename(to_path):
            to_path = os.path.join(to_path, 'index.html')
        
        # Calculate the relative path
        from_dir = os.path.dirname(from_path)
        to_dir = os.path.dirname(to_path)
        
        if from_dir == to_dir:
            return os.path.basename(to_path)
        
        # Count the number of directories to go up
        from_parts = from_dir.split('/')
        to_parts = to_dir.split('/')
        
        # Find common prefix
        common_prefix = 0
        for i in range(min(len(from_parts), len(to_parts))):
            if from_parts[i] != to_parts[i]:
                break
            common_prefix += 1
        
        # Calculate relative path
        up_dirs = ['..'] * (len(from_parts) - common_prefix)
        down_dirs = to_parts[common_prefix:]
        
        rel_path = '/'.join(up_dirs + down_dirs)
        if rel_path:
            rel_path += '/'
        
        rel_path += os.path.basename(to_path)
        
        return rel_path
    
    def _extract_links(self, soup, current_url, depth):
        """Extract links from HTML and add them to the queue"""
        for a_tag in soup.find_all('a', href=True):
            href = a_tag['href']
            
            # Skip fragment links and JavaScript
            if href.startswith('#') or href.startswith('javascript:'):
                continue
            
            # Convert to absolute URL
            absolute_url = urljoin(current_url, href)
            
            # Skip external links
            if urlparse(absolute_url).netloc != self.domain:
                continue
            
            # Clean URL (remove fragments, etc.)
            clean_url = self._clean_url(absolute_url)
            
            # Add to queue if not visited
            if clean_url not in self.visited_urls:
                self.to_visit.append((clean_url, depth + 1))
    
    def _extract_and_download_assets(self, soup, current_url):
        """Extract and download assets (CSS, JS, images, etc.)"""
        # Process stylesheets
        for link_tag in soup.find_all('link', rel='stylesheet', href=True):
            href = link_tag['href']
            absolute_url = urljoin(current_url, href)
            self._download_asset(absolute_url)
        
        # Process scripts
        for script_tag in soup.find_all('script', src=True):
            src = script_tag['src']
            absolute_url = urljoin(current_url, src)
            self._download_asset(absolute_url)
        
        # Process images
        for img_tag in soup.find_all('img', src=True):
            src = img_tag['src']
            absolute_url = urljoin(current_url, src)
            self._download_asset(absolute_url)
        
        # Process CSS url() references
        for style_tag in soup.find_all('style'):
            css_content = style_tag.string
            if css_content:
                urls = re.findall(r'url\([\'"]?([^\'"()]+)[\'"]?\)', css_content)
                for url in urls:
                    absolute_url = urljoin(current_url, url)
                    self._download_asset(absolute_url)
    
    def _download_asset(self, url):
        """Download an asset if it's on the same domain"""
        parsed_url = urlparse(url)
        
        # Skip external assets and already visited URLs
        if parsed_url.netloc != self.domain or url in self.visited_urls:
            return
        
        self.visited_urls.add(url)
        
        # Get the file path - define this before the try block so it's available in except
        file_path = self._get_file_path(url)
        
        # Create directories if they don't exist
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        try:
            # Make the request
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
            }
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code != 200:
                self.errors.append(f"Failed to fetch asset {url}: HTTP {response.status_code}")
                
                # For CSS files, create a minimal fallback
                if url.endswith('.css') or 'text/css' in response.headers.get('Content-Type', '').lower():
                    fallback_css = "/* This is a placeholder for a CSS file that could not be downloaded */\n"
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(fallback_css)
                    self.files_downloaded += 1
                    self.total_size += len(fallback_css)
                # For JavaScript files, create a minimal fallback
                elif url.endswith('.js') or 'javascript' in response.headers.get('Content-Type', '').lower():
                    fallback_js = "// This is a placeholder for a JavaScript file that could not be downloaded\n"
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(fallback_js)
                    self.files_downloaded += 1
                    self.total_size += len(fallback_js)
                # For images, create a minimal SVG placeholder
                elif any(url.endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg']):
                    fallback_svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="200" height="150" viewBox="0 0 200 150">
  <rect width="200" height="150" fill="#f1f1f1" />
  <text x="100" y="75" font-family="Arial" font-size="12" text-anchor="middle">Image Not Found</text>
  <text x="100" y="90" font-family="Arial" font-size="10" text-anchor="middle">{os.path.basename(url)}</text>
</svg>"""
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(fallback_svg)
                    self.files_downloaded += 1
                    self.total_size += len(fallback_svg)
                
                return
            
            # Save the file
            with open(file_path, 'wb') as f:
                f.write(response.content)
            
            self.files_downloaded += 1
            self.total_size += len(response.content)
            
            # For CSS files, extract and download embedded assets
            content_type = response.headers.get('Content-Type', '').lower()
            if 'text/css' in content_type:
                self._process_css_file(response.text, url)
                
        except Exception as e:
            logger.error(f"Error downloading asset {url}: {e}")
            self.errors.append(f"Error downloading asset {url}: {str(e)}")
            
            # Create a minimal placeholder based on file type
            try:
                if url.endswith('.css'):
                    fallback_css = "/* This is a placeholder for a CSS file that could not be downloaded due to an error */\n"
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(fallback_css)
                    self.files_downloaded += 1
                    self.total_size += len(fallback_css)
                elif url.endswith('.js'):
                    fallback_js = "// This is a placeholder for a JavaScript file that could not be downloaded due to an error\n"
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(fallback_js)
                    self.files_downloaded += 1
                    self.total_size += len(fallback_js)
                elif any(url.endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg']):
                    fallback_svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="200" height="150" viewBox="0 0 200 150">
  <rect width="200" height="150" fill="#f1f1f1" />
  <text x="100" y="75" font-family="Arial" font-size="12" text-anchor="middle">Image Not Found</text>
  <text x="100" y="90" font-family="Arial" font-size="10" text-anchor="middle">{os.path.basename(url)}</text>
  <text x="100" y="105" font-family="Arial" font-size="8" text-anchor="middle">Error: {str(e)[:30]}</text>
</svg>"""
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(fallback_svg)
                    self.files_downloaded += 1
                    self.total_size += len(fallback_svg)
            except Exception as placeholder_error:
                logger.error(f"Error creating placeholder for {url}: {placeholder_error}")
    
    def _process_css_file(self, css_content, css_url):
        """Process a CSS file to extract and download referenced assets"""
        urls = re.findall(r'url\([\'"]?([^\'"()]+)[\'"]?\)', css_content)
        for url in urls:
            if url.startswith('data:'):
                continue  # Skip data URLs
            
            absolute_url = urljoin(css_url, url)
            self._download_asset(absolute_url)
