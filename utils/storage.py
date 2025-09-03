import os
from supabase import create_client, Client
from dotenv import load_dotenv
from datetime import datetime
import uuid

load_dotenv()

url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_ANON_KEY")

# Validate environment variables
if not url or not key:
    raise ValueError("SUPABASE_URL and SUPABASE_ANON_KEY must be set in environment variables")

supabase: Client = create_client(url, key)

def upload_image_to_supabase(local_image_path, bucket_name='street-view-images'):
    """
    Uploads an image to the Supabase Storage bucket and returns its public URL.

    Args:
        local_image_path (str): The path to the image file on the local system.
        bucket_name (str): The name of the Supabase storage bucket.

    Returns:
        str: The public URL of the uploaded image, or None if failed.
    """
    try:
        print(f"DEBUG: Uploading image from {local_image_path} to bucket '{bucket_name}'")
        
        # Check if the local file exists
        if not os.path.exists(local_image_path):
            print(f"Error: Local file does not exist: {local_image_path}")
            return None
        
        # Check file size
        file_size = os.path.getsize(local_image_path)
        print(f"DEBUG: File size: {file_size} bytes")
        
        if file_size == 0:
            print("Error: File is empty")
            return None
        
        # Generate a unique filename to avoid overwrites
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        file_extension = os.path.splitext(local_image_path)[1] or '.jpg'
        file_name = f"scan_{timestamp}_{unique_id}{file_extension}"
        
        print(f"DEBUG: Generated filename: {file_name}")

        # Read the local file as binary data
        with open(local_image_path, 'rb') as f:
            file_data = f.read()

        print(f"DEBUG: Read {len(file_data)} bytes from file")

        # Upload the file to the bucket
        try:
            print("DEBUG: Attempting upload to Supabase...")
            response = supabase.storage.from_(bucket_name).upload(file_name, file_data, file_options={'content-type': 'image/jpeg'})
            
            print(f"DEBUG: Upload response: {response}")
            
            # Check if upload was successful
            if hasattr(response, 'error') and response.error:
                print(f"Error during upload: {response.error}")
                return None
            
            # Get the public URL
            print("DEBUG: Getting public URL...")
            public_url_response = supabase.storage.from_(bucket_name).get_public_url(file_name)
            
            if isinstance(public_url_response, str):
                public_url = public_url_response
            elif hasattr(public_url_response, 'publicUrl'):
                public_url = public_url_response.publicUrl
            elif hasattr(public_url_response, 'public_url'):
                public_url = public_url_response.public_url
            else:
                print(f"DEBUG: Unexpected public URL response format: {public_url_response}")
                # Construct URL manually as fallback
                public_url = f"{url}/storage/v1/object/public/{bucket_name}/{file_name}"
            
            print(f"Image successfully uploaded. Public URL: {public_url}")
            return public_url
            
        except Exception as upload_error:
            print(f"Error during upload operation: {upload_error}")
            
            # Try to handle specific error cases
            error_message = str(upload_error).lower()
            if 'bucket' in error_message and 'not found' in error_message:
                print(f"Bucket '{bucket_name}' does not exist. Please create it in your Supabase dashboard.")
            elif 'permission' in error_message or 'unauthorized' in error_message:
                print("Permission denied. Check your Supabase RLS policies and API key permissions.")
            elif 'duplicate' in error_message:
                print("File with this name already exists. This shouldn't happen with UUIDs.")
            
            return None
            
    except FileNotFoundError:
        print(f"Error: Could not find file: {local_image_path}")
        return None
    except PermissionError:
        print(f"Error: Permission denied accessing file: {local_image_path}")
        return None
    except Exception as e:
        print(f"Error: Unexpected error occurred: {e}")
        import traceback
        print(f"DEBUG: Full traceback: {traceback.format_exc()}")
        return None

def delete_image_from_supabase(file_url, bucket_name='street-view-images'):
    """
    Deletes an image from Supabase storage using its public URL.
    
    Args:
        file_url (str): The public URL of the file to delete.
        bucket_name (str): The name of the Supabase storage bucket.
        
    Returns:
        bool: True if successful, False otherwise.
    """
    try:
        # Extract filename from URL
        # URL format: https://your-project.supabase.co/storage/v1/object/public/bucket-name/filename
        if f'/object/public/{bucket_name}/' in file_url:
            filename = file_url.split(f'/object/public/{bucket_name}/')[-1]
        else:
            print(f"Error: Could not extract filename from URL: {file_url}")
            return False
        
        print(f"DEBUG: Attempting to delete {filename} from bucket {bucket_name}")
        
        response = supabase.storage.from_(bucket_name).remove([filename])
        
        if hasattr(response, 'error') and response.error:
            print(f"Error deleting file: {response.error}")
            return False
        
        print(f"Successfully deleted {filename}")
        return True
        
    except Exception as e:
        print(f"Error deleting file: {e}")
        return False

def list_bucket_files(bucket_name='street-view-images', limit=100):
    """
    Lists files in a Supabase storage bucket.
    
    Args:
        bucket_name (str): The name of the bucket to list.
        limit (int): Maximum number of files to return.
        
    Returns:
        list: List of file objects, or empty list if error.
    """
    try:
        response = supabase.storage.from_(bucket_name).list(limit=limit)
        
        if hasattr(response, 'error') and response.error:
            print(f"Error listing files: {response.error}")
            return []
        
        files = response if isinstance(response, list) else []
        print(f"Found {len(files)} files in bucket '{bucket_name}'")
        return files
        
    except Exception as e:
        print(f"Error listing bucket files: {e}")
        return []

def create_bucket_if_not_exists(bucket_name='street-view-images', public=True):
    """
    Creates a storage bucket if it doesn't exist.
    
    Args:
        bucket_name (str): Name of the bucket to create.
        public (bool): Whether the bucket should be public.
        
    Returns:
        bool: True if bucket exists or was created, False otherwise.
    """
    try:
        # Try to list files (this will fail if bucket doesn't exist)
        response = supabase.storage.from_(bucket_name).list(limit=1)
        
        if hasattr(response, 'error') and response.error:
            error_message = str(response.error).lower()
            if 'not found' in error_message or 'does not exist' in error_message:
                print(f"Bucket '{bucket_name}' does not exist. Attempting to create...")
                
                # Create the bucket
                create_response = supabase.storage.create_bucket(bucket_name, public=public)
                
                if hasattr(create_response, 'error') and create_response.error:
                    print(f"Error creating bucket: {create_response.error}")
                    return False
                
                print(f"Successfully created bucket '{bucket_name}'")
                return True
            else:
                print(f"Error checking bucket: {response.error}")
                return False
        
        print(f"Bucket '{bucket_name}' already exists")
        return True
        
    except Exception as e:
        print(f"Error with bucket operations: {e}")
        return False

# Test the storage functions
if __name__ == "__main__":
    print("Testing Supabase storage functions...")
    
    # Test bucket creation
    bucket_exists = create_bucket_if_not_exists()
    if not bucket_exists:
        print("❌ Could not create or access bucket")
        exit(1)
    
    # Test file listing
    files = list_bucket_files()
    print(f"Current files in bucket: {len(files)}")
    
    # Test upload (create a small test image)
    test_image_path = "test_upload.jpg"
    try:
        from PIL import Image
        import io
        
        # Create a small test image
        test_img = Image.new('RGB', (100, 100), color='red')
        test_img.save(test_image_path)
        
        print(f"Created test image: {test_image_path}")
        
        # Test upload
        public_url = upload_image_to_supabase(test_image_path)
        
        if public_url:
            print(f"✅ Upload successful: {public_url}")
            
            # Test delete
            if delete_image_from_supabase(public_url):
                print("✅ Delete successful")
            else:
                print("❌ Delete failed")
        else:
            print("❌ Upload failed")
        
        # Clean up test file
        if os.path.exists(test_image_path):
            os.remove(test_image_path)
            
    except ImportError:
        print("PIL not available, skipping upload test")
    except Exception as e:
        print(f"Test failed with error: {e}")