import os
from dotenv import load_dotenv
import logging
import socket
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

def load_and_validate_secrets():
    """
    Loads environment variables and validates presence of critical secrets.
    """
    load_dotenv()
    
    required_keys = [
        'DATABASE_URL',
        'REDIS_URL',
        'SECRET_KEY',
        'DEBUG'
    ]
    
    missing = [key for key in required_keys if not os.getenv(key)]
    
    if missing:
        error_msg = f"CRITICAL: Missing required environment variables: {', '.join(missing)}"
        logger.critical(error_msg)
        raise EnvironmentError(error_msg)
        
    # Mask secrets in logs
    masked_secrets = {
        key: '********' if key in ['SECRET_KEY', 'DATABASE_URL', 'REDIS_URL', 'SUPABASE_KEY'] else os.getenv(key)
        for key in required_keys
    }
    
    logger.info(f"Secrets loaded and validated: {masked_secrets}")
    return True

def test_ipv6_connection(url):
    """
    Tests connectivity to a service URL using IPv6 if applicable.
    """
    try:
        parsed = urlparse(url)
        hostname = parsed.hostname
        port = parsed.port
        
        # Default ports if missing
        if not port:
            if parsed.scheme == 'postgres': port = 5432
            elif parsed.scheme == 'redis': port = 6379
            elif parsed.scheme == 'http': port = 80
            elif parsed.scheme == 'https': port = 443
            
        if not hostname or not port:
            return False

        # Attempt to get address info for IPv6
        try:
             # This will try to resolve AAAA record or connect via IPv6
             # For localhost, ensure [::1] is used if intending simple IPv6 test
             # or just check if host resolves to IPv6
            addr_info = socket.getaddrinfo(hostname, port, socket.AF_INET6, socket.SOCK_STREAM)
            family, socktype, proto, canonname, sockaddr = addr_info[0]
            
            with socket.socket(family, socktype, proto) as s:
                s.settimeout(2)
                s.connect(sockaddr)
                logger.info(f"IPv6 connection successful to {hostname}:{port}")
                return True
                
        except socket.gaierror:
             logger.warning(f"No IPv6 address found for {hostname}, skipping IPv6 test.")
             return None # Not strictly a failure if host is IPv4 only
             
    except Exception as e:
        logger.error(f"IPv6 connection failed to {url}: {e}")
        return False

def startup_check():
    """
    Runs all security and connectivity checks.
    """
    print("Running Security & Health Checks...")
    
    # 1. Secret Validation
    try:
        load_and_validate_secrets()
        print("[PASS] Secret Validation")
    except Exception as e:
        print(f"[FAIL] Secret Validation: {e}")
        return False

    # 2. Connection Checks
    checks = {
        "Database": os.getenv("DATABASE_URL"),
        "Redis": os.getenv("REDIS_URL")
    }
    
    all_passed = True
    for service, url in checks.items():
        if url:
            result = test_ipv6_connection(url)
            if result is True:
                print(f"[PASS] {service} IPv6 Connectivity")
            elif result is False:
                print(f"[WARN] {service} IPv6 Connectivity Failed (Is service running?)")
                # Don't fail hard on connectivity if just validating config, but good to know
            else:
                 print(f"[INFO] {service} IPv6 Skipped (Not configured/resolvable)")
    
    return True

if __name__ == "__main__":
    startup_check()
