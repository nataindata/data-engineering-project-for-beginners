# Data Pipeline using Airflow for Beginners | Data Engineering Project 

### 🎥 Watch Youtube tutorial: https://youtu.be/L-uZoB0M-JA
Real case project to give you a hands-on experience in creating your own Airflow pipeline and grasping what Idempotency, Partitioning, and Backfilling are.

## 🧭 Plan:

Pull OpenWeather API data → Data in data lake as Parquet files on GCP platform → Staging to Production tables in Data Warehouse (BigQuery)

🏆 Run the pipeline with Airflow using [Coder](https://coder.com/) - an open-source cloud development environment you download and host in any cloud. It deploys in seconds and provisions the infrastructure, IDE, language, and tools you want. Used as the best practice in Palantir, Dropbox, Discord, and many more. 

Absolutely FREE, a few clicks to launch, and super user-friendly. 

Let’s set up the things:

### PART 1

First, make sure your Docker is running. https://docs.docker.com/desktop/install/mac-install/

Then open your terminal and run  the command to install Coder

```bash
curl -L https://coder.com/install.sh | sh
```

next start coder with the command

```bash
coder server
```

Open browser and navigate to [http://localhost:3000](http://localhost:3000/) → Create your user

💣 Boom, the platform is up and running!

Now Click Templates → Starter Templates → pick Docker containers

After it's provisioned let’s edit it a little: Dockerfile → Edit files → Add these lines:
```
    python3 \
    python3-pip \
```

main.tf → Edit files → Add these after terraform block:
(or copy from https://registry.coder.com/modules/apache-airflow)
```
module "airflow" {
  source   = "registry.coder.com/modules/apache-airflow/coder"
  version  = "1.0.13"
  agent_id = coder_agent.main.id
}
```

Click build and Publish

Now let’s create a workspace from the template: 
click Workspaces → Create → Choose your newly built template → Click Airflow button → Create user → Tada 🎉 

Now your Airflow instance ready & steady 🏎️



### PART 2

Set up Connection to Google Cloud Platform - we’ll need a GCP Service Account (like credentials to access google platform programmatically):

1. Create GCP account (it has free credits for the newbies, so don’t worry about the cost https://cloud.google.com/free/docs/free-cloud-features); 
2. Console Access: Go to the GCP Console, navigate to the IAM & Admin section, and select Service Accounts.
3. Create Service Account: Click on "Create Service Account", provide a name, description, and click "Create".
4. Grant Access: Assign the appropriate role Editor (just for the simplification)
5. Create Key: Click on "Create Key", select JSON, and then "Create". This downloads a JSON key file. Keep this file secure, as it provides API access to your GCP resources.
6. In Airflow Connections tab find “google_cloud_default” → under Keyfile JSON → insert WHOLE json file contents → Save

Set up variables 

1. In GCP create new project → Get the ID
1. create account in OpenWeather API https://openweathermap.org/ → get API key
2. In Airflow Variable tab create variables 

```bash
weather-api-key = ‘API_KEY’
bq_data_warehouse_project = ‘your project ID’
gcs-bucket = ‘weather-tutorial’
```


