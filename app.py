import os
import logging
import uuid
from flask import Flask, render_template, request, redirect, url_for, jsonify, flash, session
from werkzeug.utils import secure_filename
import threading

from scraper import WebsiteScraper

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Create the Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "default_secret_key")

# Dictionary to store active scraping tasks
scraping_tasks = {}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/scrape', methods=['POST'])
def scrape():
    url = request.form.get('url')
    max_depth = int(request.form.get('max_depth', 1))
    download_assets = request.form.get('download_assets') == 'on'
    
    if not url:
        flash('Please enter a URL to scrape', 'danger')
        return redirect(url_for('index'))
    
    # Create a unique task ID for this scraping job
    task_id = str(uuid.uuid4())
    
    # Create base directory for this scrape
    base_dir = os.path.join('static', 'downloads', task_id)
    os.makedirs(base_dir, exist_ok=True)
    
    # Initialize the scraper
    scraper = WebsiteScraper(url, base_dir, max_depth, download_assets)
    
    # Store task info
    scraping_tasks[task_id] = {
        'scraper': scraper,
        'url': url,
        'status': 'starting',
        'progress': 0,
        'files_downloaded': 0,
        'total_size': 0,
        'errors': []
    }
    
    # Start scraping in a background thread
    def run_scraper():
        try:
            scraping_tasks[task_id]['status'] = 'running'
            scraper.start_scraping()
            scraping_tasks[task_id]['status'] = 'completed'
        except Exception as e:
            logger.error(f"Error in scraping task: {e}")
            scraping_tasks[task_id]['status'] = 'failed'
            scraping_tasks[task_id]['errors'].append(str(e))
    
    thread = threading.Thread(target=run_scraper)
    thread.daemon = True
    thread.start()
    
    return redirect(url_for('results', task_id=task_id))

@app.route('/results/<task_id>')
def results(task_id):
    if task_id not in scraping_tasks:
        flash('Task not found', 'danger')
        return redirect(url_for('index'))
    
    task_info = scraping_tasks[task_id]
    download_path = os.path.join('static', 'downloads', task_id)
    return render_template('results.html', task_id=task_id, task_info=task_info, download_path=download_path)

@app.route('/status/<task_id>')
def status(task_id):
    if task_id not in scraping_tasks:
        return jsonify({'error': 'Task not found'}), 404
    
    task = scraping_tasks[task_id]
    scraper = task['scraper']
    
    return jsonify({
        'status': task['status'],
        'progress': scraper.progress,
        'files_downloaded': scraper.files_downloaded,
        'total_size': scraper.total_size,
        'errors': scraper.errors
    })

@app.errorhandler(404)
def page_not_found(e):
    return render_template('index.html', error="Page not found"), 404

@app.errorhandler(500)
def server_error(e):
    return render_template('index.html', error="Server error occurred"), 500
