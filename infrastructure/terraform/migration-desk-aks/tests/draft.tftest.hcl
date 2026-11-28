mock_provider "azurerm" {}

variables {
  location            = "eastus"
  resource_group_name = "migration-desk-mock"
  node_subnet_id      = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/migration-desk-mock/providers/Microsoft.Network/virtualNetworks/mock/subnets/mock"
  tenant_id           = "00000000-0000-0000-0000-000000000000"
}

run "private_cluster_draft" {
  command = plan

  assert {
    condition = (
      azurerm_kubernetes_cluster.draft.private_cluster_enabled &&
      !azurerm_kubernetes_cluster.draft.private_cluster_public_fqdn_enabled &&
      azurerm_kubernetes_cluster.draft.network_profile[0].outbound_type == "userDefinedRouting"
    )
    error_message = "The draft must use a private API and must not request provider-managed load-balancer egress."
  }

  assert {
    condition = (
      azurerm_kubernetes_cluster.draft.default_node_pool[0].node_count == 2 &&
      azurerm_kubernetes_cluster.draft.default_node_pool[0].vm_size == "Standard_D4s_v5"
    )
    error_message = "The draft system pool must use two Standard_D4s_v5 nodes."
  }
}
