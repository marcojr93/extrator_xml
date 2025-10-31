import streamlit as st
import pandas as pd
import xml.etree.ElementTree as ET
from io import BytesIO
from criptografia import SecureDataProcessor
from agents.validador import buscar_regras_fiscais_nfe



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
    # Sistema de abas para evitar perda de dados na navegação
    if st.session_state.get('agentes_processados', False):
        # Se agentes foram processados, mostrar seletor de modo
        # Definir índice baseado no estado da navegação
        indice_inicial = 1 if st.session_state.get('navegacao_revisao', False) else 0
        
        modo = st.selectbox(
            "Selecione o modo:",
            ["Processamento de XML", "Revisão e Edição"],
            index=indice_inicial,
            key="modo_selecao"
        )
        
        # Atualizar estado baseado na seleção
        if modo == "Revisão e Edição":
            st.session_state.navegacao_revisao = True
            # Importar e executar função de revisão diretamente
            from view.revisao import exibir_pagina_revisao
            exibir_pagina_revisao()
            return  # Sair da função para não mostrar o resto
        else:
            st.session_state.navegacao_revisao = False
    
    # Código atual do Streamlit (extrair_dados_xml interface)
    st.title("Extrator de Nota Fiscal Eletrônica (NF-e XML)")

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
        
        # Salvar dados na sessão para edição imediata
        st.session_state.cabecalho_df = cabecalho_criptografado
        st.session_state.produtos_df = produtos_criptografado
        st.session_state.arquivo_xml_nome = uploaded_file.name
        st.session_state.xml_carregado = True
        
        # Mostrar seletor de modo logo após upload
        modo = st.selectbox(
            "Selecione o modo:",
            ["Visualização dos Dados", "Edição do XML", "Análise com IA"],
            index=0,
            key="modo_pos_upload"
        )
        
        if modo == "Visualização dos Dados":
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
                                
                                # Armazenar resultado do analista para o tributarista
                                st.session_state['resultado_analista'] = resultado_analista
                                
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

        # Botão do Tributarista - Calcular Delta (só aparece após análise do analista)
        if 'resultado_analista' in st.session_state and 'resultado_validador' in st.session_state:
            st.markdown("---")
            st.subheader("🧮 Cálculo Tributário")
            
            resultado_analista_stored = st.session_state['resultado_analista']
            resultado_validador_stored = st.session_state['resultado_validador']
            
            # Verificar se há dados suficientes para cálculo
            if resultado_analista_stored.get('status') in ['sucesso', 'parcial']:
                st.info("💰 Calcule as diferenças de impostos e possíveis multas baseado na análise realizada.")
                
                if st.button("🧮 Calcular Delta", type="primary", help="Calcula diferenças entre impostos pagos vs devidos e possíveis multas"):
                    with st.spinner("Calculando delta tributário com IA especializada..."):
                        try:
                            # Executar cálculo tributário
                            resultado_tributarista = calcular_delta_tributario(
                                st.session_state['cabecalho_dados'],
                                st.session_state['produtos_dados'],
                                resultado_analista_stored,
                                resultado_validador_stored
                            )
                            
                            if resultado_tributarista['status'] in ['sucesso', 'parcial']:
                                # Mostrar relatório híbrido do tributarista
                                st.subheader("💰 Relatório de Cálculo Tributário")
                                
                                with st.expander("🧮 Relatório Completo de Cálculos", expanded=True):
                                    st.markdown(resultado_tributarista['relatorio_hibrido'])
                                
                                # Botões para download
                                col1, col2 = st.columns(2)
                                
                                with col1:
                                    relatorio_tributario = resultado_tributarista['relatorio_hibrido']
                                    st.download_button(
                                        label="📊 Baixar Relatório Tributário",
                                        data=relatorio_tributario,
                                        file_name=f"relatorio_calculo_tributario_{resultado_tributarista['timestamp_calculo'].replace(':', '-').replace(' ', '_')}.md",
                                        mime="text/markdown"
                                    )
                                
                                with col2:
                                    # Gerar CSV da tabela resumo se disponível
                                    tabela_resumo = resultado_tributarista.get('tabela_resumo', {})
                                    if tabela_resumo.get('linhas'):
                                        import io
                                        csv_buffer = io.StringIO()
                                        
                                        # Escrever cabeçalho
                                        if tabela_resumo.get('cabecalho'):
                                            csv_buffer.write(','.join(tabela_resumo['cabecalho']) + '\n')
                                        
                                        # Escrever linhas
                                        for linha in tabela_resumo['linhas']:
                                            csv_buffer.write(','.join(str(item) for item in linha) + '\n')
                                        
                                        st.download_button(
                                            label="📋 Baixar Tabela (CSV)",
                                            data=csv_buffer.getvalue(),
                                            file_name=f"tabela_delta_impostos_{resultado_tributarista['timestamp_calculo'].replace(':', '-').replace(' ', '_')}.csv",
                                            mime="text/csv"
                                        )
                                
                                # Exibir alertas críticos
                                analise_riscos = resultado_tributarista.get('analise_riscos', {})
                                if analise_riscos:
                                    risco = analise_riscos.get('risco_autuacao', '').lower()
                                    if risco == 'alto':
                                        st.error("🚨 RISCO ALTO de autuação fiscal identificado!")
                                    elif risco == 'médio':
                                        st.warning("⚠️ RISCO MÉDIO de autuação fiscal identificado.")
                                    
                                    if analise_riscos.get('valor_total_exposicao'):
                                        valor_exposicao = analise_riscos['valor_total_exposicao']
                                        st.metric(
                                            label="💸 Valor Total de Exposição",
                                            value=f"R$ {valor_exposicao:,.2f}",
                                            delta=None
                                        )
                                
                                # Mostrar resumo das multas se existirem
                                calculo_multas = resultado_tributarista.get('calculo_multas', {})
                                if calculo_multas.get('total_multas'):
                                    with st.expander("⚠️ Resumo de Multas Potenciais", expanded=False):
                                        col1, col2, col3 = st.columns(3)
                                        
                                        with col1:
                                            st.metric(
                                                label="💸 Total Multas",
                                                value=f"R$ {calculo_multas['total_multas']:,.2f}"
                                            )
                                        
                                        with col2:
                                            st.metric(
                                                label="📉 Multa Mínima",
                                                value=f"R$ {calculo_multas.get('multa_minima', 0):,.2f}"
                                            )
                                        
                                        with col3:
                                            st.metric(
                                                label="📈 Multa Máxima", 
                                                value=f"R$ {calculo_multas.get('multa_maxima', 0):,.2f}"
                                            )
                                
                                st.success("✅ Cálculos concluídos! Verifique o relatório detalhado.")
                                
                            else:
                                st.error("Erro no cálculo tributário")
                                st.write(resultado_tributarista['relatorio_hibrido'])
                                
                        except ImportError:
                            st.error("Módulo de cálculo tributário não encontrado")
                        except Exception as e:
                            st.error(f"Erro no cálculo tributário: {str(e)}")
            else:
                st.warning("⚠️ Execute primeiro a análise de discrepâncias para calcular o delta tributário.")

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

        st.success("Extração concluída com sucesso!")


def exibir_resultados_processamento():
    """Exibe os resultados do processamento dos agentes a partir do session_state"""
    try:
        # Recuperar dados do session_state
        resultado_validador = st.session_state.get('resultado_validador', {})
        resultado_analista = st.session_state.get('resultado_analista', {})
        resultado_tributarista = st.session_state.get('resultado_tributarista', {})
        resumo_execucao = st.session_state.get('resumo_execucao', {})
        arquivo_nome = st.session_state.get('arquivo_xml_nome', 'arquivo')
        timestamp_proc = st.session_state.get('timestamp_processamento', 'unknown')
        
        # Recriar resultado_completo
        resultado_completo = {
            'status': 'sucesso',
            'validador': resultado_validador,
            'analista': resultado_analista, 
            'tributarista': resultado_tributarista,
            'resumo_execucao': resumo_execucao,
            'timestamp_processamento': timestamp_proc
        }
        
        # Exibir resumo executivo
        st.success("Processamento concluído com sucesso!")
        
        # Mostrar resumo executivo
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Oportunidades", resumo_execucao.get('total_oportunidades', 0))
        with col2:
            st.metric("Discrepâncias", resumo_execucao.get('total_discrepancias', 0))
        with col3:
            st.metric("Soluções", resumo_execucao.get('total_solucoes', 0))
        with col4:
            st.metric("Produtos", resumo_execucao.get('produtos_analisados', 0))
        
        # Botões de ação
        st.info("Dados processados e salvos na sessão. Clique para revisar:")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("Ir para Revisão", type="primary", key="goto_revisao_persistent"):
                st.session_state.navegacao_revisao = True
                st.success("Clique em 'Revisão e Edição' no seletor acima para continuar!")
        
        with col2:
            # Gerar PDF com key único para evitar conflitos
            try:
                pdf_data = gerar_relatorio_pdf(resultado_completo, arquivo_nome)
                if pdf_data:
                    st.download_button(
                        label="Download Relatório PDF",
                        data=pdf_data,
                        file_name=f"relatorio_fiscal_{timestamp_proc.replace(':', '-')[:19]}.pdf",
                        mime="application/pdf",
                        type="secondary",
                        key="download_pdf_persistent"
                    )
                else:
                    st.error("Erro ao gerar relatório PDF")
            except Exception as e:
                st.error(f"Erro ao gerar PDF: {str(e)}")
        
        # Dropdown para visualizar relatório tributarista
        resultado_tributarista = resultado_completo.get('tributarista', {})
        if resultado_tributarista.get('relatorio_hibrido'):
            with st.expander("Ver Relatório Tributário Completo"):
                st.markdown(resultado_tributarista['relatorio_hibrido'])
        
    except Exception as e:
        st.error(f"Erro ao exibir resultados: {str(e)}")
        st.session_state.agentes_processados = False

def salvar_dados_temporarios(cabecalho_df, produtos_df, resultado_completo, nome_arquivo):
    """Salva dados em arquivo temporário JSON para persistência"""
    import json
    import os
    from datetime import datetime
    
    try:
        dados_temporarios = {
            'timestamp_salvamento': datetime.now().isoformat(),
            'arquivo_xml_nome': nome_arquivo,
            'cabecalho_df': cabecalho_df.to_dict('records'),
            'produtos_df': produtos_df.to_dict('records'),
            'resultado_validador': resultado_completo.get('validador', {}),
            'resultado_analista': resultado_completo.get('analista', {}),
            'resultado_tributarista': resultado_completo.get('tributarista', {}),
            'resumo_execucao': resultado_completo.get('resumo_execucao', {}),
            'timestamp_processamento': resultado_completo.get('timestamp_processamento')
        }
        
        # Salvar no diretório raiz do projeto
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        arquivo_temp = os.path.join(base_dir, 'temp_nfe_data.json')
        
        with open(arquivo_temp, 'w', encoding='utf-8') as f:
            json.dump(dados_temporarios, f, ensure_ascii=False, indent=2)
            
        st.success("Dados salvos em arquivo temporário")
        
    except Exception as e:
        st.warning(f"Erro ao salvar dados temporários: {str(e)}")


def gerar_relatorio_pdf(resultado_completo, nome_arquivo):
    """Gera relatório PDF com insights dos 3 agentes"""
    try:
        from reportlab.lib.pagesizes import letter, A4
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        from reportlab.lib import colors
        from io import BytesIO
        from datetime import datetime
        
        # Buffer para PDF
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        styles = getSampleStyleSheet()
        story = []
        
        # Título
        titulo_style = ParagraphStyle('CustomTitle', parent=styles['Title'], fontSize=18, spaceAfter=30)
        story.append(Paragraph("Relatório de Análise Fiscal", titulo_style))
        story.append(Spacer(1, 12))
        
        # Informações básicas
        story.append(Paragraph(f"<b>Arquivo:</b> {nome_arquivo}", styles['Normal']))
        story.append(Paragraph(f"<b>Data do Processamento:</b> {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}", styles['Normal']))
        story.append(Spacer(1, 20))
        
        # Resumo Executivo
        resumo = resultado_completo.get('resumo_execucao', {})
        story.append(Paragraph("<b>RESUMO EXECUTIVO</b>", styles['Heading2']))
        
        # Tabela de métricas
        dados_metricas = [
            ['Métrica', 'Valor'],
            ['Produtos Analisados', str(resumo.get('produtos_analisados', 0))],
            ['Oportunidades Identificadas', str(resumo.get('total_oportunidades', 0))],
            ['Discrepâncias Encontradas', str(resumo.get('total_discrepancias', 0))],
            ['Soluções Propostas', str(resumo.get('total_solucoes', 0))]
        ]
        
        tabela_metricas = Table(dados_metricas)
        tabela_metricas.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 14),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        story.append(tabela_metricas)
        story.append(Spacer(1, 20))
        
        # Oportunidades do Validador
        validador = resultado_completo.get('validador', {})
        oportunidades = validador.get('oportunidades', [])
        
        if oportunidades:
            story.append(Paragraph("<b>OPORTUNIDADES IDENTIFICADAS</b>", styles['Heading2']))
            for i, oport in enumerate(oportunidades, 1):
                story.append(Paragraph(f"<b>{i}. {oport.get('tipo', 'N/A')}</b>", styles['Heading3']))
                story.append(Paragraph(f"<b>Produto:</b> {oport.get('produto', 'N/A')}", styles['Normal']))
                story.append(Paragraph(f"<b>Descrição:</b> {oport.get('descricao', 'N/A')}", styles['Normal']))
                story.append(Paragraph(f"<b>Impacto:</b> {oport.get('impacto', 'N/A')}", styles['Normal']))
                story.append(Paragraph(f"<b>Ação Recomendada:</b> {oport.get('acao_recomendada', 'N/A')}", styles['Normal']))
                story.append(Spacer(1, 12))
        
        # Discrepâncias
        discrepancias = validador.get('discrepancias', [])
        if discrepancias:
            story.append(Paragraph("<b>DISCREPÂNCIAS ENCONTRADAS</b>", styles['Heading2']))
            for i, disc in enumerate(discrepancias, 1):
                story.append(Paragraph(f"<b>{i}. {disc.get('tipo', 'N/A')} ({disc.get('gravidade', 'N/A')})</b>", styles['Heading3']))
                story.append(Paragraph(f"<b>Produto:</b> {disc.get('produto', 'N/A')}", styles['Normal']))
                story.append(Paragraph(f"<b>Problema:</b> {disc.get('problema', 'N/A')}", styles['Normal']))
                story.append(Paragraph(f"<b>Correção:</b> {disc.get('correcao', 'N/A')}", styles['Normal']))
                story.append(Spacer(1, 12))

        # Relatório Final do Analista (se disponível)
        analista = resultado_completo.get('analista', {})
        if analista.get('status') == 'sucesso' and analista.get('relatorio_final'):
            story.append(Paragraph("<b>ANÁLISE DETALHADA DO ANALISTA</b>", styles['Heading2']))
            story.append(Spacer(1, 12))
            
            # Processar relatório final do analista (markdown)
            relatorio_analista = analista.get('relatorio_final', '')
            
            # Processar markdown simples
            linhas_analista = relatorio_analista.split('\n')
            for linha in linhas_analista:
                linha = linha.strip()
                if not linha:
                    story.append(Spacer(1, 6))
                    continue
                
                if linha.startswith('##'):
                    titulo = linha.replace('##', '').strip()
                    story.append(Paragraph(f"<b>{titulo}</b>", styles['Heading3']))
                elif linha.startswith('**') and linha.endswith('**'):
                    texto_negrito = linha.replace('**', '').strip()
                    story.append(Paragraph(f"<b>{texto_negrito}</b>", styles['Normal']))
                elif linha.startswith('- '):
                    item = linha.replace('- ', '').strip()
                    story.append(Paragraph(f"• {item}", styles['Normal']))
                else:
                    if linha and not linha.startswith('---'):
                        story.append(Paragraph(linha, styles['Normal']))
            
            story.append(Spacer(1, 20))
        
        # Relatório Híbrido do Tributarista (COMPLETO)
        tributarista = resultado_completo.get('tributarista', {})
        if tributarista.get('status') == 'sucesso' and tributarista.get('relatorio_hibrido'):
            story.append(Paragraph("<b>RELATÓRIO TRIBUTÁRIO COMPLETO</b>", styles['Heading2']))
            story.append(Spacer(1, 12))
            
            # Converter markdown do relatório híbrido para PDF
            relatorio_markdown = tributarista.get('relatorio_hibrido', '')
            
            # Processar o markdown linha por linha
            linhas = relatorio_markdown.split('\n')
            for linha in linhas:
                linha = linha.strip()
                if not linha:
                    story.append(Spacer(1, 6))
                    continue
                
                # Títulos principais (##)
                if linha.startswith('## '):
                    titulo = linha.replace('## ', '').strip()
                    story.append(Paragraph(f"<b>{titulo}</b>", styles['Heading3']))
                    story.append(Spacer(1, 8))
                
                # Títulos secundários (###)
                elif linha.startswith('### '):
                    subtitulo = linha.replace('### ', '').strip()
                    story.append(Paragraph(f"<b>{subtitulo}</b>", styles['Heading4']))
                    story.append(Spacer(1, 6))
                
                # Título principal (#)
                elif linha.startswith('# '):
                    titulo_principal = linha.replace('# ', '').strip()
                    story.append(Paragraph(f"<b>{titulo_principal}</b>", styles['Heading2']))
                    story.append(Spacer(1, 10))
                
                # Tabelas markdown (|)
                elif '|' in linha and not linha.startswith('|---'):
                    # Processar tabela markdown simples
                    colunas = [col.strip() for col in linha.split('|') if col.strip()]
                    if colunas:
                        # Criar linha de tabela simples
                        linha_tabela = ' | '.join(colunas)
                        story.append(Paragraph(linha_tabela, styles['Normal']))
                
                # Lista com bullet points (-)
                elif linha.startswith('- '):
                    item = linha.replace('- ', '').strip()
                    story.append(Paragraph(f"• {item}", styles['Normal']))
                
                # Texto em negrito (**texto**)
                elif '**' in linha:
                    # Substituir **texto** por <b>texto</b>
                    linha_formatada = linha.replace('**', '<b>', 1).replace('**', '</b>', 1)
                    # Continuar substituindo se houver mais
                    while '**' in linha_formatada:
                        linha_formatada = linha_formatada.replace('**', '<b>', 1).replace('**', '</b>', 1)
                    story.append(Paragraph(linha_formatada, styles['Normal']))
                
                # Separadores (---)
                elif linha.startswith('---'):
                    story.append(Spacer(1, 12))
                
                # Texto normal
                else:
                    if linha:
                        story.append(Paragraph(linha, styles['Normal']))
            
            story.append(Spacer(1, 20))
        
        # Gerar PDF
        doc.build(story)
        buffer.seek(0)
        return buffer.getvalue()
        
    except ImportError:
        st.error("Biblioteca reportlab não instalada. Execute: pip install reportlab")
        return None
    except Exception as e:
        st.error(f"Erro ao gerar PDF: {str(e)}")
        return None