# Plan-only draft. This root is exercised with a mocked provider, not applied.
# Reference only: ../azure deploys Container Apps, not AKS.
# Reference only: ../../../platform/terraform/modules/eks models the EKS control plane and node group.
terraform {
  required_version = ">= 1.7.0"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "4.30.0"
    }
  }
}

provider "azurerm" {
  features {}
  resource_provider_registrations = "none"
  use_cli                         = false
}

variable "resource_group_name" {
  type = string
}

variable "location" {
  type = string
}

variable "node_subnet_id" {
  type = string
}

variable "tenant_id" {
  type = string
}

resource "azurerm_kubernetes_cluster" "draft" {
  name                                = "migration-desk-draft"
  location                            = var.location
  resource_group_name                 = var.resource_group_name
  dns_prefix                          = "migration-desk-draft"
  private_cluster_enabled             = true
  private_cluster_public_fqdn_enabled = false
  local_account_disabled              = true
  sku_tier                            = "Free"

  default_node_pool {
    name           = "system"
    node_count     = 1
    vm_size        = "Standard_D2s_v5"
    vnet_subnet_id = var.node_subnet_id
  }

  identity {
    type = "SystemAssigned"
  }

  azure_active_directory_role_based_access_control {
    azure_rbac_enabled = true
    tenant_id          = var.tenant_id
  }

  network_profile {
    network_plugin      = "azure"
    network_plugin_mode = "overlay"
    outbound_type       = "userDefinedRouting"
  }
}
