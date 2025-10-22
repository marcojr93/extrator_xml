import streamlit as st
import pandas as pd
import xml.etree.ElementTree as ET
from io import BytesIO
from criptografia import SecureDataProcessor
from agents.validador import buscar_regras_fiscais_nfe
from agents.analista import analisar_discrepancias_nfe



def extrair_dados_xml(xml_content):
    ns = {"nfe": "http://www.portalfiscal.inf.br/nfe"}
    root = ET.fromstring(xml_content)
    infNFe = root.find(".//nfe:infNFe", ns)

    def get_text(tag, parent=infNFe, default="0"):
        return parent.findtext(tag, default=default, namespaces=ns)
    
    def converter_codigo_uf(codigo_uf):
        """Converte código numérico da UF para sigla"""
        mapa_uf = {
            '11': 'RO', '12': 'AC', '13': 'AM', '14': 'RR', '15': 'PA', '16': 'AP', '17': 'TO',
            '21': 'MA', '22': 'PI', '23': 'CE', '24': 'RN', '25': 'PB', '26': 'PE', '27': 'AL', '28': 'SE', '29': 'BA',
            '31': 'MG', '32': 'ES', '33': 'RJ', '35': 'SP',
            '41': 'PR', '42': 'SC', '43': 'RS',
            '50': 'MS', '51': 'MT', '52': 'GO', '53': 'DF'
        }
        return mapa_uf.get(str(codigo_uf), codigo_uf)

    dados = {}

    # --- IDE (Identificação da Nota) ---
    ide = infNFe.find("nfe:ide", ns)
    if ide is not None:
        dados["Número NF"] = get_text("nfe:nNF", ide)
        dados["Série"] = get_text("nfe:serie", ide)
        dados["Data Emissão"] = get_text("nfe:dhEmi", ide)
        dados["Data Saída/Entrada"] = get_text("nfe:dhSaiEnt", ide)
        dados["Natureza Operação"] = get_text("nfe:natOp", ide)
        dados["Tipo NF"] = get_text("nfe:tpNF", ide)
        dados["Modelo"] = get_text("nfe:mod", ide)
        # Converter código UF para sigla
        codigo_uf = get_text("nfe:cUF", ide)
        dados["UF"] = converter_codigo_uf(codigo_uf)
        dados["UF Código"] = codigo_uf  # Manter código original também
        dados["Finalidade"] = get_text("nfe:finNFe", ide)

    # --- EMITENTE ---
    emit = infNFe.find("nfe:emit", ns)
    if emit is not None:
        dados["Emitente CNPJ"] = get_text("nfe:CNPJ", emit)
        dados["Emitente Nome"] = get_text("nfe:xNome", emit)
        dados["Emitente Fantasia"] = get_text("nfe:xFant", emit)
        dados["Emitente IE"] = get_text("nfe:IE", emit)
        # UF do emitente com conversão
        uf_emit = get_text("nfe:enderEmit/nfe:UF", emit)
        dados["Emitente UF"] = converter_codigo_uf(uf_emit) if uf_emit != "0" else uf_emit
        dados["Emitente Município"] = get_text("nfe:enderEmit/nfe:xMun", emit)
        dados["Emitente CEP"] = get_text("nfe:enderEmit/nfe:CEP", emit)

    # --- DESTINATÁRIO ---
    dest = infNFe.find("nfe:dest", ns)
    if dest is not None:
        dados["Destinatário CNPJ"] = get_text("nfe:CNPJ", dest)
        dados["Destinatário Nome"] = get_text("nfe:xNome", dest)
        dados["Destinatário IE"] = get_text("nfe:IE", dest)
        # UF do destinatário com conversão (CRÍTICO para ICMS)
        uf_dest = get_text("nfe:enderDest/nfe:UF", dest)
        dados["Destinatário UF"] = converter_codigo_uf(uf_dest) if uf_dest != "0" else uf_dest
        dados["Destinatário Município"] = get_text("nfe:enderDest/nfe:xMun", dest)
        dados["Destinatário CEP"] = get_text("nfe:enderDest/nfe:CEP", dest)

    # --- TRANSPORTE ---
    transp = infNFe.find("nfe:transp", ns)
    if transp is not None:
        transporta = transp.find("nfe:transporta", ns)
        vol = transp.find("nfe:vol", ns)
        dados["Modalidade Frete"] = get_text("nfe:modFrete", transp)
        if transporta is not None:
            dados["Transportadora Nome"] = get_text("nfe:xNome", transporta)
            dados["Transportadora CNPJ"] = get_text("nfe:CNPJ", transporta)
            # UF da transportadora com conversão
            uf_transp = get_text("nfe:UF", transporta)
            dados["Transportadora UF"] = converter_codigo_uf(uf_transp) if uf_transp != "0" else uf_transp
        if vol is not None:
            dados["Qtde Volumes"] = get_text("nfe:qVol", vol)
            dados["Peso Líquido"] = get_text("nfe:pesoL", vol)
            dados["Peso Bruto"] = get_text("nfe:pesoB", vol)

    # --- COBRANÇA / FATURA ---
    cobr = infNFe.find("nfe:cobr", ns)
    if cobr is not None:
        fat = cobr.find("nfe:fat", ns)
        dup = cobr.find("nfe:dup", ns)
        if fat is not None:
            dados["Número Fatura"] = get_text("nfe:nFat", fat)
            dados["Valor Original"] = get_text("nfe:vOrig", fat)
            dados["Valor Líquido"] = get_text("nfe:vLiq", fat)
        if dup is not None:
            dados["Número Duplicata"] = get_text("nfe:nDup", dup)
            dados["Data Vencimento"] = get_text("nfe:dVenc", dup)
            dados["Valor Duplicata"] = get_text("nfe:vDup", dup)

    # --- TOTALIZAÇÃO ---
    total = infNFe.find(".//nfe:ICMSTot", ns)
    if total is not None:
        dados["Base ICMS"] = get_text("nfe:vBC", total)
        dados["Valor ICMS"] = get_text("nfe:vICMS", total)
        dados["Valor Produtos"] = get_text("nfe:vProd", total)
        dados["Valor NF"] = get_text("nfe:vNF", total)
        dados["Valor Frete"] = get_text("nfe:vFrete", total)
        dados["Valor IPI"] = get_text("nfe:vIPI", total)
        dados["Valor COFINS"] = get_text("nfe:vCOFINS", total)
        dados["Valor PIS"] = get_text("nfe:vPIS", total)

    # --- PRODUTOS ---
    produtos = []
    for det in infNFe.findall("nfe:det", ns):
        prod = det.find("nfe:prod", ns)
        imp = det.find("nfe:imposto", ns)
        if prod is not None:
            p = {
                "Item": det.attrib.get("nItem", "0"),
                "Código": get_text("nfe:cProd", prod),
                "Descrição": get_text("nfe:xProd", prod),
                "NCM": get_text("nfe:NCM", prod),
                "CFOP": get_text("nfe:CFOP", prod),
                "Unidade": get_text("nfe:uCom", prod),
                "Quantidade": get_text("nfe:qCom", prod),
                "Valor Unitário": get_text("nfe:vUnCom", prod),
                "Valor Total": get_text("nfe:vProd", prod),
            }
            if imp is not None:
                p["ICMS"] = get_text(".//nfe:vICMS", imp)
                p["IPI"] = get_text(".//nfe:vIPI", imp)
                p["PIS"] = get_text(".//nfe:vPIS", imp)
                p["COFINS"] = get_text(".//nfe:vCOFINS", imp)
            produtos.append(p)

    produtos_df = pd.DataFrame(produtos).fillna("0")
    cabecalho_df = pd.DataFrame([dados]).fillna("0")

    return cabecalho_df, produtos_df


# ==============================
# STREAMLIT INTERFACE
# ==============================
def welcome_screen():
    """Tela principal da aplicação XML Reader"""
    
    # Código atual do Streamlit (extrair_dados_xml interface)
    st.title("🧾 Extrator de Nota Fiscal Eletrônica (NF-e XML)")

    uploaded_file = st.file_uploader("Selecione o arquivo XML da NF-e", type=["xml"])

    if uploaded_file is not None:
        xml_content = uploaded_file.read().decode("utf-8")

        cabecalho_df, produtos_df = extrair_dados_xml(xml_content)

        # Criptografar dados automaticamente
        processor = SecureDataProcessor()
        
        # Criptografar cabecalho
        cabecalho_criptografado = processor.encrypt_sensitive_data(cabecalho_df)
        
        # Criptografar produtos  
        produtos_criptografado = processor.encrypt_sensitive_data(produtos_df)
        
        # Manter expandables normais + adicionar dropdown criptografado
        with st.expander("Dados Gerais da NF-e", expanded=True):
            st.dataframe(cabecalho_df.T, use_container_width=True)

        with st.expander("Produtos e Impostos Detalhados", expanded=False):
            st.dataframe(produtos_df, use_container_width=True)

        # NOVO - Dropdown para dados criptografados
        with st.expander("Dados Criptografados", expanded=False):
            tab1, tab2 = st.tabs(["Cabeçalho", "Produtos"])
            
            with tab1:
                st.dataframe(cabecalho_criptografado, use_container_width=True)
            
            with tab2:
                st.dataframe(produtos_criptografado, use_container_width=True)

        # Análise Fiscal com IA
        st.subheader("Busca de Regras Fiscais")
        
        if st.button("Buscar Regras Fiscais Aplicáveis", type="primary"):
            with st.spinner("Buscando regras fiscais com IA especializada..."):
                try:
                    # Executar busca de regras fiscais
                    resultado = buscar_regras_fiscais_nfe(
                        cabecalho_criptografado, 
                        produtos_criptografado
                    )
                    
                    # Armazenar resultado no session_state para uso posterior
                    st.session_state['resultado_validador'] = resultado
                    st.session_state['cabecalho_dados'] = cabecalho_criptografado
                    st.session_state['produtos_dados'] = produtos_criptografado
                    
                    if resultado['status'] == 'sucesso':
                        # Mostrar dropdown com resumo das regras
                        st.subheader("📋 Regras Fiscais Encontradas")
                        
                        with st.expander("🔍 Resumo das Principais Regras Fiscais", expanded=True):
                            st.markdown(resultado['resumo_dropdown'])
                        
                        # Mostrar detalhes das regras se disponíveis
                        if 'regras_fiscais' in resultado and resultado['regras_fiscais']:
                            st.subheader("📖 Detalhes das Regras Fiscais")
                            
                            regras = resultado['regras_fiscais']
                            
                            # Separar em abas para cada tipo de regra
                            tab1, tab2, tab3, tab4, tab5 = st.tabs([
                                "ICMS", "PIS/COFINS", "IPI", "Benefícios Fiscais", "Fórmulas de Cálculo"
                            ])
                            
                            with tab1:
                                if 'regras_icms' in regras:
                                    st.text_area("Regras ICMS:", regras['regras_icms'], height=150)
                                else:
                                    st.info("Regras ICMS não encontradas ou não aplicáveis")
                            
                            with tab2:
                                if 'regras_pis_cofins' in regras:
                                    st.text_area("Regras PIS/COFINS:", regras['regras_pis_cofins'], height=150)
                                else:
                                    st.info("Regras PIS/COFINS não encontradas")
                            
                            with tab3:
                                if 'regras_ipi' in regras:
                                    st.text_area("Regras IPI:", regras['regras_ipi'], height=150)
                                else:
                                    st.info("Regras IPI não aplicáveis para estes produtos")
                            
                            with tab4:
                                if 'beneficios_fiscais' in regras:
                                    st.text_area("Benefícios Fiscais:", regras['beneficios_fiscais'], height=150)
                                else:
                                    st.info("Benefícios fiscais não identificados")
                            
                            with tab5:
                                if 'formulas_calculo' in regras:
                                    st.text_area("Fórmulas de Cálculo:", regras['formulas_calculo'], height=150)
                                else:
                                    st.info("Fórmulas de cálculo não especificadas")
                        
                        st.success(f"✅ Busca concluída! {resultado.get('produtos_analisados', 0)} produtos analisados.")
                        
                        # Informação adicional para o usuário
                        st.info("💡 As regras fiscais foram armazenadas em memória e podem ser usadas por outros agentes para análise detalhada.")
                        
                    else:
                        st.error("Erro na busca de regras fiscais")
                        st.write(resultado['resumo_dropdown'])
                        
                except ImportError:
                    st.error("Módulo de validação fiscal não encontrado")
                except Exception as e:
                    st.error(f"Erro na análise fiscal: {str(e)}")

        # Botão do Analista - Tratar Discrepâncias (só aparece após validação)
        if 'resultado_validador' in st.session_state:
            resultado_val = st.session_state['resultado_validador']
            discrepancias = resultado_val.get('discrepancias', [])
            
            if discrepancias:
                st.markdown("---")
                st.subheader("🎯 Análise de Discrepâncias")
                
                # Mostrar resumo das discrepâncias encontradas
                st.info(f"⚠️ {len(discrepancias)} discrepância(s) encontrada(s) que necessitam de tratamento.")
                
                if st.button("🔧 Tratar Discrepâncias", type="secondary", help="Analisa as discrepâncias encontradas e propõe soluções baseadas em Lucro Real"):
                    with st.spinner("Analisando discrepâncias com IA especializada..."):
                        try:
                            # Executar análise de discrepâncias
                            resultado_analista = analisar_discrepancias_nfe(
                                st.session_state['cabecalho_dados'],
                                st.session_state['produtos_dados'],
                                resultado_val
                            )
                            
                            if resultado_analista['status'] in ['sucesso', 'parcial']:
                                # Mostrar relatório do analista
                                st.subheader("📊 Relatório de Tratamento de Discrepâncias")
                                
                                with st.expander("📋 Relatório Completo de Análise", expanded=True):
                                    st.markdown(resultado_analista['relatorio_final'])
                                
                                # Botão para download do relatório
                                relatorio_download = resultado_analista['relatorio_final']
                                st.download_button(
                                    label="📄 Baixar Relatório de Análise",
                                    data=relatorio_download,
                                    file_name=f"relatorio_analise_discrepancias_{resultado_analista['timestamp_analise'].replace(':', '-').replace(' ', '_')}.md",
                                    mime="text/markdown"
                                )
                                
                                # Exibir resumo das ações
                                plano = resultado_analista.get('plano_acao_consolidado', {})
                                if plano.get('acoes_imediatas'):
                                    st.success("✅ Análise concluída! Verifique as ações recomendadas no relatório.")
                                    
                                    with st.expander("⚡ Ações Imediatas Recomendadas", expanded=False):
                                        for acao in plano['acoes_imediatas']:
                                            st.write(f"• {acao}")
                                
                                if plano.get('consultoria_necessaria'):
                                    st.warning("👨‍💼 Algumas questões necessitam de consultoria especializada. Consulte o relatório.")
                                
                            else:
                                st.error("Erro na análise de discrepâncias")
                                st.write(resultado_analista['relatorio_final'])
                                
                        except ImportError:
                            st.error("Módulo de análise fiscal não encontrado")
                        except Exception as e:
                            st.error(f"Erro na análise de discrepâncias: {str(e)}")
            else:
                if resultado_val.get('status') == 'sucesso':
                    st.success("✅ Nenhuma discrepância crítica foi identificada na validação!")
                    st.info("💡 A nota fiscal está em conformidade com as regras analisadas.")

        # Criação do Excel para download
        output = BytesIO()
        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
            cabecalho_df.to_excel(writer, sheet_name="Cabecalho", index=False)
            produtos_df.to_excel(writer, sheet_name="Produtos", index=False)
        output.seek(0)

        st.download_button(
            label="📥 Baixar Excel da NF-e",
            data=output,
            file_name="nfe_dados_extraidos.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

        st.success("✅ Extração concluída com sucesso!")